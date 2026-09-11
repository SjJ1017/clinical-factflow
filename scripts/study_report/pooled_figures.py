"""Pooled source/outcome figures and paired role/novelty contrasts."""
import json,itertools
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import PercentFormatter
from analyze_figure_revision import case_values,stat
FINAL={'Correct':'#238b59','Incorrect':'#cf4948'}
MARK={'Correct':'o','Incorrect':'^'}

def cells(es,key):
    labels=['Correct','Incorrect'] if key=='truth' else ['Majority','Minority']
    return [(g,f,[e for e in es if e[key]==g and e['final']==f]) for f in FINAL for g in labels]

def fmt(x):return 'NA' if x is None else ('<0.001' if x<.001 else f'{x:.3f}')
def p_label(name,x):return name+('<0.001' if x is not None and x<.001 else '='+fmt(x))
def test_text(t):
    s=t['effect']
    if s['mean'] is None:return f"Final {t['final'].lower()}: no paired panels"
    ci='CI unavailable' if s['lo'] is None else f"95% CI [{100*s['lo']:+.1f}, {100*s['hi']:+.1f}]"
    return f"Final {t['final'].lower()}: Δ {100*s['mean']:+.1f} pp, {ci}; n={s['n']}, {p_label('p',t['p'])}, {p_label('q',t['q'])}"

def source_figure(E,R,kind,version):
    if version=='boxplot':return boxplot_grid(E,R,kind)
    key='truth' if kind=='correctness' else 'status'
    edges=[e for e in R['pooled_edges'] if kind=='correctness' or e['panel_kind']=='two_one']
    fig,axes=plt.subplots(2,1,figsize=(13.6,9.5));fig.subplots_adjust(left=.17,right=.98,top=.84,bottom=.22,hspace=.76)
    title='Source diagnosis and later fact uptake' if kind=='correctness' else 'Majority status and later fact uptake'
    fig.suptitle(title+' — pooled transitions',fontsize=16,y=.98)
    handles=[Line2D([],[],marker='s',ls='',color=c,label='Final '+f.lower()) for f,c in FINAL.items()]
    if version=='scatter':handles += [Line2D([],[],marker=m,ls='',color='#405461',label='Source '+g.lower()) for g,m in MARK.items()]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.55,.939),ncol=len(handles),frameon=False)
    records=[]
    for ax,receiver in zip(axes,['self','peers']):
        es=[e for e in edges if (e['seat']==e['target'])==(receiver=='self') and e['rate'] is not None]
        ax.set_title('Self-retention rate' if receiver=='self' else 'Peer uptake rate',loc='left',fontweight='bold',pad=10)
        groups=cells(es,key);summaries=[]
        for i,(g,f,rs) in enumerate(groups):
            cv=case_values(rs);s=stat(list(cv.values()));summaries.append((g,f,rs,cv,s))
            records.append({'receiver':receiver,'group':g,'final':f,'stat':s,'case_values':cv,'edges':len(rs)})
        if version=='scatter':
            # A common point band for correctness; only majority/minority separates bands.
            for e in es:
                y=0 if kind=='correctness' else (0 if e['status']=='Majority' else .85)
                ax.scatter(e['rate'],y+E.jitter((e['case'],e['condition'],e['round'],e['seat'],e['target']),.26),s=19,c=FINAL[e['final']],marker=MARK[e['truth']],alpha=.43,linewidths=0)
            start=.64 if kind=='correctness' else 1.45
            ticks=([0] if kind=='correctness' else [0,.85]);labs=(['All source edges'] if kind=='correctness' else ['Majority edges','Minority edges'])
            for k,f in enumerate(FINAL):ax.axhspan(start+k*.5-.115,start+k*.5+.375,color=FINAL[f],alpha=.075,zorder=0)
            for i,(g,f,rs,cv,s) in enumerate(summaries):
                y=start+i*.25;ticks.append(y);labs.append(f'{g} / final {f.lower()}  (n={s["n"]})')
                if s['mean'] is not None:
                    if s['lo'] is not None:ax.plot([s['lo'],s['hi']],[y,y],color=FINAL[f],lw=2)
                    ax.scatter(s['mean'],y,c=FINAL[f],marker=MARK[g] if key=='truth' else 'D',s=44,edgecolors='white',linewidth=.5,zorder=4)
            ax.set_ylim(start+1.05,-.4)
        else:
            ticks=list(range(4));labs=[]
            for i,(g,f,rs,cv,s) in enumerate(summaries):
                labs.append(f'{g} / final {f.lower()}  (n={s["n"]})')
                if not cv:continue
                ax.boxplot(list(cv.values()),positions=[i],vert=False,widths=.46,patch_artist=True,manage_ticks=False,showfliers=True,boxprops={'facecolor':FINAL[f]+'35','edgecolor':FINAL[f]},medianprops={'color':FINAL[f],'linewidth':2},whiskerprops={'color':FINAL[f]},capprops={'color':FINAL[f]},flierprops={'marker':'.','markersize':3,'markeredgecolor':FINAL[f]})
                if s['lo'] is not None:ax.plot([s['lo'],s['hi']],[i+.28,i+.28],color=FINAL[f],lw=2)
                ax.scatter(s['mean'],i+.28,c=FINAL[f],marker='D',s=24)
            ax.set_ylim(3.7,-.5)
        ax.set_yticks(ticks,labs,fontsize=8);ax.tick_params(axis='y',length=0);ax.set_xlim(-.01,1.01);ax.xaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='x',alpha=.18);ax.set_xlabel('Fraction of source facts retained')
        ts=[t for t in R['pooled_tests'] if t['kind']==kind and t['receiver']==receiver]
        for j,t in enumerate(ts):ax.text(0,-.32-j*.10,test_text(t),transform=ax.transAxes,fontsize=8.2,color=FINAL[t['final']])
    E.foot(fig,('Dots: individual edges; summary markers: case means and 95% case-bootstrap CI.' if version=='scatter' else 'Boxes: case means, median and IQR; whiskers: 1.5 IQR. Diamonds / bars: mean / 95% case-bootstrap CI.')+'\nΔ: within-panel '+('correct − incorrect' if kind=='correctness' else 'minority − majority')+'; equal weight per case. p: case sign-flip; q: BH across 8 planned tests. Final = R3 system answer.\nR1→R2 and R2→R3 pooled. Correct = exact or accepted hierarchy (S+L); incorrect = D; unclassified excluded. n in rows = cases; n in tests = paired cases.')
    E.DETAILS[f'{kind}-pooled-{version}']=records
    return fig

def boxplot_grid(E,R,kind):
    key='truth' if kind=='correctness' else 'status';labels=['Correct','Incorrect'] if key=='truth' else ['Majority','Minority']
    edges=[e for e in R['pooled_edges'] if kind=='correctness' or e['panel_kind']=='two_one']
    fig,axes=plt.subplots(2,3,figsize=(14.4,9.2),sharey=True)
    fig.subplots_adjust(left=.07,right=.985,top=.82,bottom=.23,wspace=.24,hspace=.71)
    title='Source diagnosis and later fact uptake' if kind=='correctness' else 'Majority status and later fact uptake'
    fig.suptitle(title+' - pooled transitions',fontsize=16,y=.98)
    fig.legend(handles=[Line2D([],[],marker='s',ls='',color=c,label='Final '+f.lower()) for f,c in FINAL.items()],loc='upper center',bbox_to_anchor=(.5,.935),ncol=2,frameon=False)
    records=[]
    for i,receiver in enumerate(['self','peers']):
        for j,outcome in enumerate(['All','Correct','Incorrect']):
            ax=axes[i,j];es=[e for e in edges if (e['seat']==e['target'])==(receiver=='self') and e['rate'] is not None and (outcome=='All' or e['final']==outcome)]
            ax.set_title('All classified finals' if outcome=='All' else 'Final '+outcome.lower(),fontweight='bold',color=FINAL.get(outcome,'#243b43'),pad=15)
            if outcome!='All':ax.set_facecolor(FINAL[outcome]+'0c')
            for g,f,rs in cells(es,key):
                if outcome!='All' and f!=outcome:continue
                cv=case_values(rs);st=stat(list(cv.values()));records.append({'panel':outcome,'receiver':receiver,'group':g,'final':f,'stat':st,'case_values':cv,'edges':len(rs)})
                x=labels.index(g)+((-.19 if f=='Correct' else .19) if outcome=='All' else 0)
                if cv:
                    ax.boxplot(list(cv.values()),positions=[x],widths=.27 if outcome=='All' else .43,patch_artist=True,manage_ticks=False,boxprops={'facecolor':FINAL[f]+'40','edgecolor':FINAL[f]},medianprops={'color':FINAL[f],'linewidth':2},whiskerprops={'color':FINAL[f]},capprops={'color':FINAL[f]},flierprops={'marker':'.','markersize':3,'markeredgecolor':FINAL[f]})
                    if st['lo'] is not None:ax.plot([x,x],[st['lo'],st['hi']],color=FINAL[f],lw=1.6)
                    ax.scatter(x,st['mean'],color=FINAL[f],marker='D',s=26,zorder=4)
                ax.text(x,1.025,f"n={st['n']}",ha='center',va='bottom',fontsize=8,color=FINAL[f])
            ax.set_xticks([0,1],labels);ax.set_xlabel('Source diagnosis' if key=='truth' else 'Source majority status',fontsize=9);ax.set_xlim(-.55,1.55);ax.set_ylim(-.02,1.10);ax.set_yticks([0,.25,.5,.75,1]);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.17)
            if j==0:ax.set_ylabel('Self-retention rate' if receiver=='self' else 'Peer uptake rate',fontweight='bold')
            if outcome=='All':
                ax.text(.5,-.24,'Final groups are shown together;\nstratified paired tests appear at right.',transform=ax.transAxes,ha='center',va='top',fontsize=8,color='#52646a')
            else:
                t=next(t for t in R['pooled_tests'] if t['kind']==kind and t['receiver']==receiver and t['final']==outcome);st=t['effect']
                txt='No paired panels' if st['mean'] is None else f"Δ {100*st['mean']:+.1f} pp; paired n={st['n']}\n95% CI [{100*st['lo']:+.1f}, {100*st['hi']:+.1f}] pp\n{p_label('p',t['p'])}; {p_label('q',t['q'])}"
                ax.text(.5,-.24,txt,transform=ax.transAxes,ha='center',va='top',fontsize=8.4,color=FINAL[outcome])
    E.foot(fig,'Boxes: case means; median and IQR; whiskers: 1.5 IQR. Diamonds / bars: mean / 95% case-bootstrap CI. All-final column repeats the two strata.\nΔ: paired within-panel '+('correct - incorrect' if kind=='correctness' else 'minority - majority')+'; p: case sign-flip; q: BH across 8 tests. Final = R3 system answer.\nR1-R2 and R2-R3 pooled. Correct = S+L, incorrect = D. Unclassified excluded. Box n = cases; test n = paired cases.')
    E.DETAILS[f'{kind}-pooled-boxplot']=records
    return fig

def factorial(E,R,receiver):
    edges=[e for e in R['factorial_edges'] if e['panel_kind']=='two_one' and (e['seat']==e['target'])==(receiver=='self')]
    fig,axes=plt.subplots(2,3,figsize=(13.5,8.4));fig.subplots_adjust(left=.075,right=.89,bottom=.13,top=.87,wspace=.32,hspace=.42)
    fig.suptitle(('Self retention' if receiver=='self' else 'Peer uptake')+' — source correctness × majority status',fontsize=16,y=.974)
    records=[]
    for ax,cond in zip(axes.flat,E.CONDS+['average']):
        grid=np.full((2,2),np.nan);entries={}
        for i,truth in enumerate(['Correct','Incorrect']):
            for j,status in enumerate(['Majority','Minority']):
                ds={c:case_values([e for e in edges if e['condition']==c and e['truth']==truth and e['status']==status]) for c in E.CONDS}
                if cond=='average':
                    valid=[v for v in ds.values() if v];v=float(np.mean([np.mean(list(z.values())) for z in valid])) if valid else None
                    # Cluster bootstrap resamples the same case IDs in all five settings.
                    ids=sorted(set().union(*(z.keys() for z in valid)));bs=[]
                    if len(ids)>1:
                        for ix in np.random.default_rng(20260911).integers(0,len(ids),(2000,len(ids))):
                            means=[np.mean([z[ids[k]] for k in ix if ids[k] in z]) for z in valid if any(ids[k] in z for k in ix)]
                            if means:bs.append(float(np.mean(means)))
                    lo,hi=np.quantile(bs,[.025,.975]).tolist() if bs else (None,None)
                    s={'mean':v,'n':len(ids),'lo':lo,'hi':hi};k=len(valid)
                else:s=stat(list(ds[cond].values()));k=1 if s['mean'] is not None else 0
                entries[i,j]=(s,k);grid[i,j]=s['mean'] if s['mean'] is not None else np.nan
                records.append({'condition':cond,'receiver':receiver,'truth':truth,'status':status,'settings':k,**s})
        im=ax.pcolormesh(np.arange(3)-.5,np.arange(3)-.5,grid,cmap='YlGnBu',vmin=0,vmax=1);ax.set_xlim(-.5,1.5);ax.set_ylim(1.5,-.5);ax.set_aspect('equal')
        for (i,j),(s,k) in entries.items():
            label='NA\nn=0' if s['mean'] is None else f"{s['mean']:.1%}\nn={s['n']}"+(f", {k}/5 settings" if cond=='average' else '')+('' if s['lo'] is None else f"\n[{100*s['lo']:.1f}, {100*s['hi']:.1f}]%")
            ax.text(j,i,label,ha='center',va='center',fontsize=8.8,color='white' if s['mean'] is not None and s['mean']>.58 else '#183843')
        ax.set_xticks([0,1],['Majority','Minority']);ax.set_yticks([0,1],['Correct','Incorrect']);ax.tick_params(length=0);ax.set_title(E.CN.get(cond,'Equal mean of available settings'),fontsize=11)
    cb=fig.colorbar(im,cax=fig.add_axes([.93,.21,.016,.57]));cb.ax.yaxis.set_major_formatter(PercentFormatter(1));cb.set_label('Mean source-fact uptake rate')
    E.foot(fig,'R1→R2 and R2→R3 pooled; strict 2:1 panels; S+L versus D. Cells: mean, case n and 95% case-bootstrap CI.\nSource → panel → round → condition → case averaging. Overall: equal setting-cell means; absent cells are excluded and setting coverage is shown.')
    E.DETAILS[f'factorial-pooled-{receiver}']=records
    return fig

def contrast_fig(E,rows,metric,title,interaction=False):
    rounds=[2,3] if interaction else [1,2,3]
    fig,axes=plt.subplots(1,len(rounds),figsize=(13.6,6),sharex=True,sharey=True);fig.subplots_adjust(left=.18,right=.97,top=.8,bottom=.17,wspace=.2)
    fig.suptitle(title,fontsize=15,y=.974);E.role_legend(fig) if not interaction else None
    allstats=[]
    for ax,rd in zip(axes,rounds):
        ax.axvline(0,ls='--',c='#8d9fa3',lw=1);ax.grid(axis='x',alpha=.16);ax.set_title(f'R{rd}')
        yt=[];yl=[]
        for z,info in enumerate(['shared','split']):
            fields=['all'] if interaction else E.FIELDS
            for j,f in enumerate(fields):
                y=z*(1 if interaction else 4)+j;yt.append(y);yl.append(info.capitalize()+('' if interaction else ' / '+E.FN[f]))
                if interaction:s=next(r for r in rows if r['info']==info and r['round']==rd and r['metric']==metric)
                else:
                    by=defaultdict(dict)
                    for r in rows:
                        if r['round']==rd and r['field']==f and r['condition'] in [info+'-generic',info+'-specialist']:by[r['case']][r['condition']]=r[metric]
                    vs=[v[info+'-specialist']-v[info+'-generic'] for v in by.values() if len(v)==2 and all(x is not None for x in v.values())];s=stat(vs)
                c=E.FC.get(f,'#3b617e');allstats.append({'info':info,'round':rd,'field':f,'metric':metric,**s})
                if s['mean'] is not None:
                    ax.plot([s['lo'],s['hi']],[y,y],c=c,lw=2);ax.scatter(s['mean'],y,c=c,marker='D',s=40)
                    ax.text(.98,y+.29,f"{100*s['mean']:+.1f} pp  [{100*s['lo']:+.1f}, {100*s['hi']:+.1f}]",transform=ax.get_yaxis_transform(),ha='right',fontsize=8)
        ax.set_yticks(yt,yl);ax.set_ylim(max(yt)+.75,-.5);ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('New-fact role effect − old-fact role effect' if interaction else 'Specialist − generic');ax.set_xlim(-.3,.3) if interaction else ax.set_xlim(-.55,.55) if metric=='uptake_prime' else ax.set_xlim(-.2,.5)
    E.foot(fig,'Paired case differences; diamonds: mean; bars: 95% case-bootstrap CI. Same information allocation compared within case.\n'+('Role effect = specialist − generic, averaged across three professions. Positive: larger role effect on new facts.' if interaction else 'Profession colors are fixed. Undefined pairs are omitted; no threshold or metric selection by setting.'))
    E.DETAILS[('novel-interaction-' if interaction else 'paired-role-')+metric]=allstats
    return fig

def export(E,R,profiles):
    for kind,name in [('correctness','05_correctness_and_final_outcome.pdf'),('majority','06_majority_advantage.pdf')]:
        with PdfPages(E.OUT/name) as pdf:
            for v in ['scatter','boxplot']:
                fig=source_figure(E,R,kind,v);pdf.savefig(E.vectorize(fig));plt.close(fig)
        E.FIGS.append(E.OUT/name)
    name='07_correctness_by_majority.pdf'
    with PdfPages(E.OUT/name) as pdf:
        for rec in ['self','peers']:
            fig=factorial(E,R,rec);pdf.savefig(E.vectorize(fig));plt.close(fig)
    E.FIGS.append(E.OUT/name)
    name='08_new_fact_preference.pdf'
    with PdfPages(E.OUT/name) as pdf:
        for scope,metric,title,percent in [('new_outputs','output_own','New output facts — own-profession share',True),('new_outputs','output_prime','New output facts — own minus other',False),('new_initial','output_own','New beyond prior outputs and initial evidence — own share',True)]:
            rows=[r for r in R['novel_profiles'] if r['scope']==scope]
            fig=E.profile_fig(rows,metric,title,E.OUT/(scope+'_'+metric),percent);pdf.savefig(E.vectorize(fig));plt.close(fig)
        fig=contrast_fig(E,R['novel_vs_old_interactions'],'output_own','Does the role effect grow for new facts?',True);pdf.savefig(E.vectorize(fig));plt.close(fig)
    E.FIGS.append(E.OUT/name)
    name='09_paired_role_contrasts.pdf'
    with PdfPages(E.OUT/name) as pdf:
        for metric,title in [('uptake_prime','Role effect on uptake prime'),('output_own','Role effect on own-profession output share'),('output_prime','Role effect on output prime')]:
            fig=contrast_fig(E,profiles,metric,title);pdf.savefig(E.vectorize(fig));plt.close(fig)
    E.FIGS.append(E.OUT/name)
    E.DETAILS['pooled-inference']=R['pooled_tests']
