"""Publication figures: vector PDFs, auditable per-point values, no API calls."""
from pathlib import Path
from collections import defaultdict,Counter
import json,math,hashlib,itertools,zipfile
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import PercentFormatter
from pypdf import PdfReader,PdfWriter
from scipy.stats import t
from tokenizers import Tokenizer
from analyze import ROOT,DEST,CONDS,FIELDS,avg,summarize,components
from judge_names import load_runs

OUT=ROOT/'findings/medcase24-figures'
FC={'clinical':'#287e78','laboratory':'#b27b29','imaging':'#8264b4'}
CC=dict(zip(CONDS,['#7e8994','#3d65a8','#cc913b','#14867c','#b55c86']))
CN={'shared-generic':'Shared / generic','shared-specialist':'Shared / specialist','split-generic':'Split / generic','split-specialist':'Split / specialist','split-mismatched':'Split / mismatched'}
FN={'clinical':'Clinical','laboratory':'Lab / pathology','imaging':'Imaging'}
BASE={'unit':'equivalence','scheme':'fractional','match':'equivalence'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.titlesize':12,'axes.labelsize':10,'pdf.fonttype':42,'ps.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#abb8b8','xtick.color':'#41565b','ytick.color':'#41565b','text.color':'#243b43','axes.labelcolor':'#243b43','savefig.facecolor':'white'})
FIGS=[];DETAILS={};AUDIT={'api_calls':0,'selected_profile_algorithm':BASE,'ci':'95% case bootstrap (2000 draws); source scatter summaries additionally show t sensitivity','point_unit':'case-agent for profiles; source-recipient edge for source scatter'}

def select(r,**kw):return all(r.get(k)==v for k,v in kw.items())
def jitter(key,scale=.15):return (int(hashlib.sha256(str(key).encode()).hexdigest()[:8],16)/0xffffffff-.5)*2*scale

def stats(rows,key='value'):
    bc=defaultdict(list)
    for r in rows:
        if r.get(key) is not None:bc[r['case']].append(r[key])
    a=[avg(v) for v in bc.values()];s=summarize(a);s['t_lo']=s['t_hi']=None
    if len(a)<2:s['lo']=s['hi']=None
    else:
        h=float(t.ppf(.975,len(a)-1)*np.std(a,ddof=1)/np.sqrt(len(a)));s['t_lo']=s['mean']-h;s['t_hi']=s['mean']+h
    return s

def foot(fig,text):fig.text(.5,.022,text,ha='center',va='bottom',fontsize=8,color='#52646a')
def vectorize(fig):
    for ax in fig.axes:
        for c in ax.collections:
            c.set_rasterized(False)
            if type(c).__name__=='QuadMesh':c.set_edgecolor('face')
    return fig

def save(pdf,fig):
    vectorize(fig).savefig(pdf,format='pdf',bbox_inches=None)
    FIGS.append(pdf)
    plt.close(fig)

def role_legend(fig,extra=[]):
    handles=[Line2D([],[],marker='o',ls='',color=c,label=FN[f],markersize=5) for f,c in FC.items()]+extra
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.58,.943),ncol=len(handles),frameon=False,fontsize=9)

def profile_fig(rows,metric,title,path,percent=False):
    fig,axes=plt.subplots(1,3,figsize=(14.4,7.2),sharex=True,sharey=True);fig.subplots_adjust(left=.17,right=.985,top=.85,bottom=.13,wspace=.22)
    fig.suptitle(title,fontsize=16,y=.985)
    role_legend(fig,[Line2D([],[],color='#223c43',marker='D',label='Case-mean overall',markersize=4)])
    summary=[]
    for rd,ax in zip([1,2,3],axes):
        ax.set_title(f'R{rd}',fontweight='bold',pad=14);ax.axvline(0,color='#95a9aa',lw=.8,ls='--',zorder=0);ax.grid(axis='x',color='#e5e9e9',lw=.6);ax.set_axisbelow(True)
        for i,c in enumerate(CONDS):
            ps=[r for r in rows if r['condition']==c and r['round']==rd]
            assert len(ps)==72
            for r in ps:
                if r[metric] is not None:ax.scatter(r[metric],i+jitter((r['case'],r['seat']),.17),s=15,c=FC[r['field']],alpha=.64,edgecolors='none',zorder=2)
            for j,f in enumerate(FIELDS+['all']):
                st=stats([r for r in ps if f=='all' or r['field']==f],metric);y=i+.29+j*.073;color=FC.get(f,'#223c43')
                if st['mean'] is not None:
                    if st['lo'] is not None:ax.plot([st['lo'],st['hi']],[y,y],color=color,lw=1.5)
                    ax.scatter(st['mean'],y,marker='D',s=17,color=color,zorder=3)
                summary.append({'condition':c,'round':rd,'field':f,'metric':metric,**st})
            missing=sum(r[metric] is None for r in ps)
            ax.text(.98,i-.29,f'{72-missing}/72'+(f'  |  NA {missing}' if missing else ''),ha='right',va='center',fontsize=7.5,color='#6b7b80',transform=ax.get_yaxis_transform())
        ax.set_ylim(4.85,-.55);ax.set_yticks(range(5));ax.tick_params(axis='y',length=0,pad=15);ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_xlim((0,1) if percent else (-1,1));ax.set_xticks([0,.25,.5,.75,1] if percent else [-1,-.5,0,.5,1]);ax.set_xlabel('Own-profession output share' if percent else ('Own - other output share' if metric=='output_prime' else 'Own - other uptake rate'))
    axes[0].set_yticklabels([CN[c] for c in CONDS],fontweight='normal')
    foot(fig,'Dots: case-agent ratios. Diamonds and bars: mean and 95% case-bootstrap CI. Undefined ratios are omitted, not set to zero.')
    DETAILS[path.stem]={'metric':metric,'algorithm':BASE,'summary':summary,'points':[{k:r[k] for k in ['case','condition','round','seat','field',metric]} for r in rows]}
    return fig

def token_data(runs):
    cache=OUT/'token-clock.json'
    tokenizer_path=next((Path.home()/'.cache/huggingface/hub/models--BAAI--bge-base-en-v1.5/snapshots').glob('*/tokenizer.json'))
    tok=Tokenizer.from_file(str(tokenizer_path));tok.no_truncation();tok.no_padding()
    signature={'viewer_sha256':hashlib.sha256((ROOT/'findings/medcase24-trace-viewer.html').read_bytes()).hexdigest(),'tokenizer_sha256':hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(),'position':'supporting-span end; missing span -> end of turn','order':'round then A/B/C','version':1}
    if cache.exists():
        prior=json.loads(cache.read_text())
        if prior['signature']==signature:return prior
    results=[];matched=unlocated=0
    for run in runs:
        eq=[(a,b) for a,b,x,y in run['scores'] if min(x,y)>=5.28];adj=defaultdict(set)
        for a,b in eq:adj[a].add(b);adj[b].add(a)
        turns=[]
        for c in sorted([c for c in run['cards'] if c['channel']=='output'],key=lambda c:(c['round'],c['agent'])):
            enc=tok.encode(c['text'],add_special_tokens=False);n=len(enc.ids);starts=np.asarray([a for a,b in enc.offsets]);events=[]
            for f in c['facts']:
                spans=f['spans'];end16=min(spans,key=lambda s:s[0])[1] if spans else None
                if end16 is not None:
                    prefix=c['text'].encode('utf-16-le')[:end16*2].decode('utf-16-le');end=len(prefix);position=int(np.searchsorted(starts,end,side='left'));matched+=1
                else:position=n;unlocated+=1
                assert 0<=position<=n
                events.append([position,f['id'],end16 is not None])
            turns.append({'id':c['id'],'round':c['round'],'agent':c['agent'],'tokens':n,'events':events})
        for rd in [0,1,2,3]:
            used=[c for c in turns if rd==0 or c['round']==rd];events=[];total=0
            for c in used:
                events.extend((total+e[0],e[1],c['id'],e[2]) for e in c['events']);total+=c['tokens']
            parent={};count=0;trajectory=[[0,0,0]]
            def find(x):
                while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
                return x
            grouped=defaultdict(list)
            for pos,node,_,_ in events:grouped[pos].append(node)
            for pos,nodes in sorted(grouped.items()):
                for node in nodes:
                    if node in parent:continue
                    parent[node]=node;count+=1
                    for other in adj[node]:
                        if other not in parent:continue
                        a,b=find(node),find(other)
                        if a!=b:parent[a]=b;count-=1
                trajectory.append([pos,count,len(parent)])
            trajectory.append([total,count,len(parent)])
            assert count==len(components(parent,eq))
            results.append({'case':run['case'],'condition':run['condition'],'round':rd,'tokens':total,'trajectory':trajectory,'events':events})
    result={'signature':signature,'located_mentions':matched,'fallback_mentions':unlocated,'runs':results};cache.write_text(json.dumps(result,separators=(',',':')));return result

def token_fig(td,rd):
    rs=[r for r in td['runs'] if r['round']==rd];common=min(r['tokens'] for r in rs);grid=np.linspace(0,common,180)
    fig,axes=plt.subplots(1,2,figsize=(13.5,6.5));fig.subplots_adjust(top=.81,bottom=.18,left=.075,right=.985,wspace=.21)
    fig.suptitle('Distinct output facts along the token clock'+(' - R1 to R3' if rd==0 else f' - R{rd} only'),fontsize=16,y=.98)
    fig.legend(handles=[Line2D([],[],color=CC[c],label=CN[c],lw=2) for c in CONDS],ncol=5,loc='upper center',bbox_to_anchor=(.5,.926),frameon=False)
    rows=[]
    for c in CONDS:
        cs=[r for r in rs if r['condition']==c];ys=[]
        for r in cs:
            a=np.asarray(r['trajectory']);v=a[np.searchsorted(a[:,0],grid,side='right')-1,1];ys.append(v)
            axes[1].step(a[:,0],a[:,1],where='post',color=CC[c],alpha=.17,lw=.6)
            axes[1].scatter(a[-1,0],a[-1,1],color=CC[c],s=10,alpha=.55)
        a=np.asarray(ys);boot=a[np.random.default_rng(20260910).integers(0,24,(2000,24))].mean(axis=1);mean=a.mean(axis=0);lo,hi=np.quantile(boot,[.025,.975],axis=0)
        axes[0].plot(grid,mean,color=CC[c],lw=2,label=CN[c]);axes[0].fill_between(grid,lo,hi,color=CC[c],alpha=.10)
        rows.append({'condition':c,'round':rd,'tokens':grid.tolist(),'mean':mean.tolist(),'lo':lo.tolist(),'hi':hi.tolist()})
    axes[0].set_title('Same token budget: 24 cases per setting');axes[1].set_title('Complete individual trajectories: 120 traces')
    for ax in axes:ax.set_xlabel('Estimated visible output tokens');ax.set_ylabel('Distinct facts (equivalence components)');ax.grid(alpha=.17);ax.set_ylim(bottom=0);ax.set_xlim(left=0)
    foot(fig,'BAAI/bge-base-en-v1.5 tokenizer; quote-end positions; output only. Left: common support, no extrapolation.\nParallel turns ordered by round, then A/B/C for accounting. Components may merge as new nodes appear.')
    DETAILS[f'token-R{rd}']=rows
    return fig

def flow_figs(raw):
    rows=[r for r in raw['graphs'] if select(r,**BASE)];DETAILS['source-heatmap-ratios']=rows;out=[];allgrids=[]
    for rd in [2,3]:
        grids=[];records=[]
        for cond in CONDS+['average']:
            grid=np.full((3,3),np.nan);ns=np.zeros((3,3),int)
            for i,a in enumerate(FIELDS):
                for j,b in enumerate(FIELDS):
                    ss=[r for r in rows if r['round']==rd and r['from']==a and r['to']==b and (cond=='average' or r['condition']==cond)]
                    if cond=='average':
                        means=[avg([r['uptake_prime'] for r in ss if r['condition']==c]) for c in CONDS];v=avg(means)
                    else:v=avg([r['uptake_prime'] for r in ss])
                    if v is not None:grid[i,j]=v
                    ns[i,j]=len({r['case'] for r in ss if r['uptake_prime'] is not None})
                    records.append({'round':rd,'condition':cond,'source':a,'target':b,'mean':v,'cases':int(ns[i,j])})
            grids.append((cond,grid,ns));allgrids.append(grid)
        out.append((rd,grids,records))
    limit=max(.1,math.ceil(max(np.nanmax(np.abs(g)) for g in allgrids)*10)/10)
    def draw(ax,g,ns):
        im=ax.pcolormesh(np.arange(4)-.5,np.arange(4)-.5,g,cmap='RdBu_r',vmin=-limit,vmax=limit,shading='flat');ax.set_xlim(-.5,2.5);ax.set_ylim(2.5,-.5);ax.set_aspect('equal')
        for i,j in itertools.product(range(3),repeat=2):
            v=g[i,j];label='NA' if np.isnan(v) else f'{100*v:+.1f} pp\nn={ns[i,j]}'
            ax.text(j,i,label,ha='center',va='center',fontsize=10,color='white' if abs(v)>.6*limit else '#233c43')
        ax.set_xticks(range(3),[FN[f] for f in FIELDS],fontsize=8);ax.set_yticks(range(3),[FN[f] for f in FIELDS],fontsize=8)
        ax.set_xlabel('Recipient profession');ax.set_ylabel('Source profession');ax.tick_params(length=0)
        return im
    with PdfPages(OUT/'04_source_uptake_heatmaps.pdf') as pdf:
        for rd,grids,records in out:
            fig,axes=plt.subplots(2,3,figsize=(13.5,8.6));fig.subplots_adjust(left=.075,right=.89,top=.88,bottom=.12,wspace=.4,hspace=.5)
            fig.suptitle(f'Source-resolved uptake prime - R{rd-1} to R{rd}',fontsize=16,y=.975)
            for ax,(cond,g,ns) in zip(axes.flat,grids):im=draw(ax,g,ns);ax.set_title(CN.get(cond,'Equal mean of five settings'),fontsize=11)
            cb=fig.colorbar(im,cax=fig.add_axes([.925,.19,.014,.60]));cb.ax.yaxis.set_major_formatter(PercentFormatter(1));cb.set_label('Own-profession uptake - other-profession uptake')
            foot(fig,'Categories follow the recipient profession. Diagonal = self retention. Average = arithmetic mean of the five setting means.\nFractional labels; within-source equivalence units; direct equivalence matching. n = independent cases with defined prime.')
            pdf.savefig(vectorize(fig));plt.close(fig)
            for cond,g,ns in grids:
                fig,ax=plt.subplots(figsize=(5.9,5.5));fig.subplots_adjust(top=.82,left=.20,right=.80,bottom=.19)
                im=draw(ax,g,ns);ax.set_title(f'{CN.get(cond,"Mean of five settings")}\nR{rd-1} to R{rd}',pad=13)
                fig.colorbar(im,cax=fig.add_axes([.85,.25,.03,.49])).ax.yaxis.set_major_formatter(PercentFormatter(1))
                foot(fig,'Uptake prime; categories follow recipient profession.\nFractional labels; equivalence units; direct matching.')
                save(OUT/f'04_R{rd-1}-R{rd}_{cond}.pdf',fig)
            DETAILS[f'flow-R{rd}']=records
    FIGS.append(OUT/'04_source_uptake_heatmaps.pdf')


def source_pop(edges,kind,rd,outcome,paired=True):
    good={'S','L'}
    rs=[r for r in edges if r['round']==rd and (outcome=='all' or outcome=='correct' and r['final_label'] in good or outcome=='wrong' and r['final_label']=='D')]
    if kind=='correctness':rs=[r for r in rs if r['label'] in good|{'D'}]
    else:rs=[r for r in rs if r['panel_kind']=='two_one']
    def group(r):return ('Correct' if r['label'] in good else 'Incorrect') if kind=='correctness' else ('Majority' if r['status']=='majority' else 'Minority')
    for r in rs:r['group']=group(r)
    if paired:
        groups=defaultdict(set)
        for r in rs:groups[(r['case'],r['condition'])].add(r['group'])
        rs=[r for r in rs if len(groups[(r['case'],r['condition'])])==2]
    return rs

def group_stats(rs):
    # A source contributes one self rate or a mean across its two peer edges.
    sources=defaultdict(list)
    for r in rs:sources[(r['case'],r['condition'],r['seat'])].append(r['rate'])
    panels=defaultdict(list)
    for (case,cond,seat),v in sources.items():panels[(case,cond)].append(avg(v))
    return stats([{'case':case,'value':avg(v)} for (case,cond),v in panels.items()])

def source_fig(edges,kind,rd,paired=True):
    fig=plt.figure(figsize=(13.8,10));gs=fig.add_gridspec(4,3,height_ratios=[2.45,.85,2.45,.85],left=.085,right=.985,top=.85,bottom=.13,hspace=.46,wspace=.14)
    labels=['Correct','Incorrect'] if kind=='correctness' else ['Majority','Minority'];markers={labels[0]:'o',labels[1]:'^'}
    title='Diagnosis correctness and subsequent fact uptake' if kind=='correctness' else 'Majority status and subsequent fact uptake'
    fig.suptitle(f'{title} - R{rd} to R{rd+1}',fontsize=16,y=.985)
    role_legend(fig,[Line2D([],[],marker=markers[g],ls='',color='#334b52',label=g,markersize=6) for g in labels])
    records=[]
    for col,outcome in enumerate(['all','correct','wrong']):
        pop=source_pop([dict(e) for e in edges],kind,rd,outcome,paired)
        for ri,receiver in enumerate(['self','peers']):
            ax=fig.add_subplot(gs[2*ri,col]);sm=fig.add_subplot(gs[2*ri+1,col]);rs=[r for r in pop if (r['seat']==r['target'])==(receiver=='self')]
            for k,g in enumerate(labels):
                ps=[r for r in rs if r['group']==g]
                for r in ps:
                    if r['rate'] is None:continue
                    ax.scatter(k+jitter((r['case'],r['condition'],r['seat'],r['target']),.26),r['rate'],s=18,marker=markers[g],c=FC[r['field']],alpha=.57,linewidths=0,zorder=2)
                st=group_stats(ps);y=1-k
                if st['mean'] is not None:
                    if st['t_lo'] is not None:sm.plot([max(0,st['t_lo']),min(1,st['t_hi'])],[y,y],color='#b6c0c2',lw=1)
                    if st['lo'] is not None:sm.plot([st['lo'],st['hi']],[y,y],color='#243f48',lw=2.5)
                    sm.scatter(st['mean'],y,marker=markers[g],s=29,color='#243f48',zorder=3)
                    sm.text(.995,y,f'n={st["n"]}',ha='right',va='center',fontsize=7.5,transform=sm.get_yaxis_transform())
                else:sm.text(.5,y,'No eligible sources',ha='center',va='center',fontsize=8,color='#8c969a')
                records.append({'kind':kind,'round':rd,'paired':paired,'outcome':outcome,'receiver':receiver,'group':g,'edges':len(ps),'sources':len({(r['case'],r['condition'],r['seat']) for r in ps}),'panels':len({(r['case'],r['condition']) for r in ps}),'stat':st})
            ax.set_xlim(-.55,1.55);ax.set_xticks([0,1],labels);ax.set_ylim(-.025,1.04);ax.set_yticks([0,.25,.5,.75,1]);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.18)
            if col==0:ax.set_ylabel('Self retention rate' if ri==0 else 'Peer uptake rate',fontweight='bold')
            else:ax.set_yticklabels([])
            if ri==0:ax.set_title({'all':'All final outcomes','correct':'Final vote correct','wrong':'Final vote incorrect'}[outcome],pad=17)
            npan=len({(r['case'],r['condition']) for r in rs});ncase=len({r['case'] for r in rs});ax.text(.5,1.015,f'{npan} panels / {ncase} cases / {len(rs)} edges',ha='center',transform=ax.transAxes,fontsize=8,color='#697d82')
            sm.set_ylim(-.5,1.5);sm.set_xlim(0,1.11);sm.set_yticks([1,0],labels if col==0 else ['',''],fontsize=8);sm.set_xticks([0,.5,1]);sm.xaxis.set_major_formatter(PercentFormatter(1));sm.spines[['top','right','left']].set_visible(False);sm.tick_params(axis='y',length=0);sm.set_xlabel('Mean and 95% CI',fontsize=8)
    foot(fig,('Paired panels with both source groups.' if paired else 'All classified sources; descriptive means are not within-panel contrasts.')+(' Source correctness: S+L versus D.' if kind=='correctness' else ' Majority identity: same-specificity diagnosis synonyms.')+'\nColor: source profession; shape: source group. Every dot is one source-recipient edge; means give equal weight to cases.\nDark bars: bootstrap CI. Thin gray bars: t sensitivity (clipped to 0-100%). Sparse final-error cohorts are exploratory.')
    DETAILS[f'{kind}-R{rd}-'+('paired' if paired else 'all')]=records
    return fig


def factorial_fig(edges,rd,cond):
    rs=[r for r in edges if r['round']==rd and r['panel_kind']=='two_one' and r['label'] in ['S','L','D'] and (cond=='all' or r['condition']==cond)]
    fig,axes=plt.subplots(1,2,figsize=(10.8,5.8));fig.subplots_adjust(left=.14,right=.88,top=.77,bottom=.19,wspace=.35)
    fig.suptitle(f'Correctness x majority status - R{rd} to R{rd+1}',fontsize=16,y=.98);fig.text(.5,.89,'All five settings' if cond=='all' else CN[cond],ha='center',fontsize=11)
    rows=[]
    for ax,receiver in zip(axes,['self','peers']):
        g=np.full((2,2),np.nan);records={}
        for i,truth in enumerate(['correct','wrong']):
            for j,status in enumerate(['majority','minority']):
                es=[r for r in rs if (r['seat']==r['target'])==(receiver=='self') and r['status']==status and (r['label'] in ['S','L'])==(truth=='correct')];st=group_stats(es)
                if st['mean'] is not None:g[i,j]=st['mean']
                records[(i,j)]=st;rows.append({'round':rd,'condition':cond,'receiver':receiver,'correctness':truth,'status':status,'edges':len(es),**st})
        cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#f0f2f2');im=ax.pcolormesh(np.arange(3)-.5,np.arange(3)-.5,g,vmin=0,vmax=1,cmap=cmap,shading='flat');ax.set_xlim(-.5,1.5);ax.set_ylim(1.5,-.5);ax.set_aspect('equal')
        for (i,j),st in records.items():
            text='NA\n0 cases' if st['mean'] is None else f'{st["mean"]*100:.1f}%\nn={st["n"]}'+('*' if st['n']<5 else '') + (f'\n[{st["lo"]*100:.1f}, {st["hi"]*100:.1f}]' if st['lo'] is not None else '\nCI unavailable')
            ax.text(j,i,text,ha='center',va='center',fontsize=11,color='white' if g[i,j]>.55 else '#243e45')
        ax.set_xticks([0,1],['Majority','Minority']);ax.set_yticks([0,1],['Correct (S+L)','Incorrect (D)']);ax.set_title('Self retention' if receiver=='self' else 'Peer uptake',pad=13);ax.tick_params(length=0)
    fig.colorbar(im,cax=fig.add_axes([.92,.24,.025,.47])).ax.yaxis.set_major_formatter(PercentFormatter(1))
    foot(fig,'Strict 2:1 source-round diagnosis panels. Mean rates, case counts and 95% bootstrap CIs.\nEach cell uses all eligible sources; groups need not share cases/panels. * Fewer than 5 cases: exploratory. NA is not zero.')
    DETAILS[f'factorial-R{rd}-{cond}']=rows
    return fig


def main():
    OUT.mkdir(exist_ok=True,parents=True);D=json.loads((DEST/'summary.json').read_text());O=json.loads((DEST/'observations.json').read_text());social=json.loads((DEST/'social-uptake-observations.json').read_text())
    profiles=[r for r in O['profiles'] if select(r,**BASE)]
    save(OUT/'01_uptake_prime.pdf',profile_fig(profiles,'uptake_prime','Professional selectivity in uptake',OUT/'01_uptake_prime.pdf'))
    with PdfPages(OUT/'02_output_preference.pdf') as pdf:
        for metric,title,percent in [('output_own','Professional preference in output - own-profession share',True),('output_prime','Professional preference in output - own minus other',False)]:
            f=profile_fig(profiles,metric,title,Path(metric),percent);pdf.savefig(vectorize(f));plt.close(f)
    FIGS.append(OUT/'02_output_preference.pdf')
    td=token_data(load_runs());AUDIT['token_clock']={k:v for k,v in td.items() if k!='runs'}
    for r in td['runs']:
        old=next(x for x in O['counts'] if x['case']==r['case'] and x['condition']==r['condition'] and x['round']==r['round'] and x['scope']==('trace' if r['round']==0 else 'round') and x['mode']=='equivalence');assert old['facts']==r['trajectory'][-1][1]
    with PdfPages(OUT/'03_facts_by_output_tokens.pdf') as pdf:
        for rd in [0,1,2,3]:f=token_fig(td,rd);pdf.savefig(vectorize(f));plt.close(f)
    FIGS.append(OUT/'03_facts_by_output_tokens.pdf');flow_figs(O)
    rolemap={(r['case'],r['condition']):r['role_by_seat'] for r in O['role_mapping']}
    edges=[dict(r,field=rolemap[(r['case'],r['condition'])][r['seat']]) for r in social['edges'] if select(r,unit='equivalence',scope='all',match='equivalence')]
    DETAILS['source-edge-points']=edges
    for kind,name in [('correctness','05_correctness_and_final_outcome.pdf'),('majority','06_majority_advantage.pdf')]:
        with PdfPages(OUT/name) as pdf:
            for rd in [1,2]:
                for paired in ([True,False] if kind=='correctness' else [True]):f=source_fig(edges,kind,rd,paired);pdf.savefig(vectorize(f));plt.close(f)
        FIGS.append(OUT/name)
    with PdfPages(OUT/'07_correctness_by_majority.pdf') as pdf:
        for cond in ['all']+CONDS:
            for rd in [1,2]:f=factorial_fig(edges,rd,cond);pdf.savefig(vectorize(f));plt.close(f)
    FIGS.append(OUT/'07_correctness_by_majority.pdf')
    primary=sorted([p for p in FIGS if p.name[:3] in [f'{i:02d}_' for i in range(1,8)] and not p.name.startswith('04_R')])
    writer=PdfWriter()
    for p in primary:writer.append(p)
    with (OUT/'00_all_figures.pdf').open('wb') as f:writer.write(f)
    FIGS.append(OUT/'00_all_figures.pdf')
    AUDIT['pdfs']={p.name:len(PdfReader(p).pages) for p in sorted(FIGS)};AUDIT['figure_count']=len(FIGS)
    assert len(FIGS)==20 and len(PdfReader(OUT/'00_all_figures.pdf').pages)==27
    (OUT/'figure-data.json').write_text(json.dumps(DETAILS,separators=(',',':'),allow_nan=False));(OUT/'audit.json').write_text(json.dumps(AUDIT,indent=2))
    print(json.dumps({'pdfs':AUDIT['pdfs'],'token_clock':AUDIT['token_clock']},indent=2))
if __name__=='__main__':main()
