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
FIGS=[];DETAILS={};AUDIT={'api_calls':0,'selected_profile_algorithm':BASE,'ci':'95% case bootstrap (2000 draws); paired sign-flip p and BH q; t sensitivity retained in revision JSON','point_unit':'case-agent for profiles; source-recipient edge for source scatter'}

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
        # Pair adjacent generic/specialist settings visually; connectors join profession means.
        for low,high,shade in [(0,1,'#edf3f8'),(2,3,'#edf6f2')]:
            ax.axhspan(low-.45,high+.55,color=shade,zorder=0)
            for j,f in enumerate(FIELDS):
                ms=[stats([r for r in rows if r['condition']==CONDS[q] and r['round']==rd and r['field']==f],metric)['mean'] for q in [low,high]]
                if all(v is not None for v in ms):ax.plot(ms,[low+.29+j*.073,high+.29+j*.073],color=FC[f],alpha=.35,lw=1,zorder=1)
        for i,c in enumerate(CONDS):
            ps=[r for r in rows if r['condition']==c and r['round']==rd]
            assert len(ps)==72
            for r in ps:
                if r[metric] is not None:ax.scatter(r[metric],i+jitter((r['case'],r['seat']),.17),s=15,c=FC[r['field']],alpha=.64,edgecolors='none',zorder=2)
            for j,f in enumerate(FIELDS+['all']):
                st=stats([r for r in ps if f=='all' or r['field']==f],metric);y=i+.29+j*.073;color=FC.get(f,'#223c43')
                if st['mean'] is not None:
                    if st['lo'] is not None:ax.plot([st['lo'],st['hi']],[y,y],color=color,lw=1.5)
                    ax.scatter(st['mean'],y,marker=('o' if c.endswith('generic') else '^' if c.endswith('mismatched') else 'D'),s=24,color=color,zorder=3)
                summary.append({'condition':c,'round':rd,'field':f,'metric':metric,**st})
            missing=sum(r[metric] is None for r in ps)
            ax.text(.98,i-.29,f'{72-missing}/72'+(f'  |  NA {missing}' if missing else ''),ha='right',va='center',fontsize=7.5,color='#6b7b80',transform=ax.get_yaxis_transform())
        ax.set_ylim(4.85,-.55);ax.set_yticks(range(5));ax.tick_params(axis='y',length=0,pad=15);ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_xlim((0,1) if percent else (-1,1));ax.set_xticks([0,.25,.5,.75,1] if percent else [-1,-.5,0,.5,1]);ax.set_xlabel('Own-profession output share' if percent else ('Own - other output share' if metric=='output_prime' else 'Own - other uptake rate'))
    axes[0].set_yticklabels([CN[c] for c in CONDS],fontweight='normal')
    foot(fig,'Dots: case-agent ratios; summary circles = generic, diamonds = specialist, triangles = mismatch. Bars: 95% case-bootstrap CI.\nShaded pairs and connectors compare generic / specialist under the same information setting. Undefined ratios are omitted.')
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
    import sys
    from pooled_figures import export
    from analyze_figure_revision import main as revise
    revise()
    revision=json.loads((OUT/'revision-analysis.json').read_text())
    export(sys.modules[__name__],revision,profiles)
    primary=sorted([p for p in FIGS if p.name[:3] in [f'{i:02d}_' for i in range(1,10)] and not p.name.startswith('04_R')])
    writer=PdfWriter()
    for p in primary:writer.append(p)
    with (OUT/'00_all_figures.pdf').open('wb') as f:writer.write(f)
    FIGS.append(OUT/'00_all_figures.pdf')
    AUDIT['pdfs']={p.name:len(PdfReader(p).pages) for p in sorted(FIGS)};AUDIT['figure_count']=len(FIGS)
    assert len(FIGS)==22 and len(PdfReader(OUT/'00_all_figures.pdf').pages)==22
    (OUT/'figure-data.json').write_text(json.dumps(DETAILS,separators=(',',':'),allow_nan=False));(OUT/'audit.json').write_text(json.dumps(AUDIT,indent=2))
    print(json.dumps({'pdfs':AUDIT['pdfs'],'token_clock':AUDIT['token_clock']},indent=2))
if __name__=='__main__':main()
