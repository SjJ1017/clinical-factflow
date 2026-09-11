// Editable scientific figures for the exploratory fact-to-outcome audit.
export function addOutcomeSlides(H){
 const {D,slide,text,box,line,arrow,dot,ink,muted,rule,blend}=H;
 const teal='#14867c',blue='#3d65a8',amber='#b27b29',red='#cf4948';
 const pp=v=>(v>=0?'+':'')+(v*100).toFixed(1),ci=r=>`[${pp(r.lo)}, ${pp(r.hi)}]`,primary=k=>D.tests.find(r=>r.key===k);
 const note='Source: findings/medcase24-fact-outcome/analysis.json and observations.json; docs/medcase24-fact-outcome.md. Offline exploratory audit. No R3 fact predictors. Outcome: R3 semantic-system S/L accepted; U counted not accepted in primary analysis, not definite error. Case-bootstrap 95% CIs (2,000); clustered inference over 24 cases. ';
 const forestAxis=(s,x,y,w,h,min,max,ticks,fmt=t=>(t*100).toFixed(0))=>{const X=v=>x+(v-min)/(max-min)*w;for(const t of ticks){line(s,[[X(t),y],[X(t),y+h]],t===0?'#99aeb7':rule,t===0?1.5:.7,t===0);text(s,fmt(t),X(t)-26,y+h+10,52,25,18,muted,false,'center');}return X;};
 // 19. Temporality and scope.
 {
  const s=slide('Fact predictors use only the first two rounds',note+'Each metric enters a separate linear probability model with case and condition fixed effects, log R1 output tokens and R1 accepted agent fraction. R1 correctness is an oracle covariate, not a deployment input.','Temporal order helps prevent leakage. It does not identify whether fact selection causes better reasoning or follows it.');
  const cards=[['R1','Initial evidence use\nInitial diagnoses',blue],['R2','Early fact flow\nEvidence coverage',teal],['R3','Final diagnosis\nAccepted or not accepted',ink]];
  cards.forEach(([a,b,c],i)=>{const x=60+i*404;box(s,x,182,354,177,blend(c,.94),c,1.3);text(s,a,x+20,201,315,42,33,c,true);text(s,b,x+20,261,315,80,27,ink);if(i)arrow(s,[[x-50,270],[x-9,270]],muted,2);});
  text(s,'12 fact metrics',62,408,350,44,32,ink,true);text(s,'Measured by the end of R2',62,466,352,70,25,muted);
  text(s,'120 traces / 24 cases',466,408,353,44,31,ink,true);text(s,'Only 13 cases vary in final outcome across settings',466,466,350,98,25,muted);
  text(s,'84 accepted finals',870,408,350,44,31,ink,true);text(s,'22 different diagnoses\n14 uncertain labels',870,466,350,85,25,muted);
  text(s,'Adjustment: case + setting + R1 token volume + R1 agent correctness',62,585,1156,41,26,ink,true);
  text(s,'Final success: 6/36 with no correct R1 agent, versus 78/84 with at least one.',62,631,1156,30,22,muted);
 }
 // 20. Report every prespecified association, not only the strongest.
 {
  const s=slide('Evidence coverage is the strongest candidate',note+'Each effect is percentage-point change in accepted final probability per one sample SD of the predictor, separately fitted. p uses finite-sample case-cluster sandwich t; q BH across all 12 primary coefficients. CI and p use different small-sample approximations.','95% case-bootstrap CI. BH q uses case-cluster t tests; no q < .05. Exploratory associations, not causal effects.');
  text(s,'Adjusted accuracy difference per 1 SD of the fact metric',61,128,1130,37,26,ink,true);
  const x=366,w=487,y=207,h=387,X=forestAxis(s,x,y,w,h,-.26,.26,[-.2,-.1,0,.1,.2]);
  text(s,'Estimate [95% CI], pp',890,174,250,25,18,muted);text(s,'BH q',1162,174,69,25,18,muted);
  D.tests.forEach((r,i)=>{const yy=220+i*32.5,c=r.key==='r2_evidence'?teal:r.key==='r1_entropy'?amber:blue;
   if(r.key==='r2_evidence')box(s,56,yy-15,1180,31,blend(teal,.95));
   text(s,r.name.replace('→','–'),62,yy-12,299,30,20,ink,r.key==='r2_evidence');line(s,[[X(r.lo),yy],[X(r.hi),yy]],c,2.3);dot(s,X(r.mean),yy,4.7,c,'diamond');text(s,`${pp(r.mean)} ${ci(r)}`,888,yy-11,259,26,18,c,r.key==='r2_evidence');text(s,r.q.toFixed(3),1164,yy-11,62,26,18,muted);
  });
  text(s,'Lower accepted accuracy',370,635,250,25,18,muted);text(s,'Higher accepted accuracy',626,635,250,25,18,muted,false,'right');
 }
 // 21. Common-scale sensitivity plot.
 {
  const s=slide('Coverage tracks outcome and the current reasoning state',note+'All rows use a common +10 percentage-point coverage scale. Primary and grading sensitivities were prespecified; R1 coverage and diagnosis-exclusion checks were targeted follow-ups after the initial audit. Conditioning on R2 correctness can control a mediator or a shared consequence, and does not orient causality.','Coverage = original source-fact units matched in the union of R2 outputs. It does not distinguish clinically useful from irrelevant evidence.');
  text(s,'Final accuracy difference for +10 pp of R2 evidence coverage',60,130,1140,39,27,ink,true);
  const get=t=>D.sensitivity.find(r=>r.key==='r2_evidence'&&r.sensitivity===t);
  const rows=[['Primary adjustment',primary('r2_evidence')],['Also control R1 coverage',D.targeted.extra[0]],['Exclude uncertain finals',get('exclude_U')],['Exclude diagnosis-tagged facts',D.targeted.extra[2]],['Require same disease / specificity',get('same_only')],['Also control R2 correctness',get('adjust_R2_correctness')]];
  const X=forestAxis(s,443,221,421,340,-.05,.25,[-.05,0,.05,.1,.15,.2,.25]);
  rows.forEach(([label,r],i)=>{let yy=245+i*52,k=.1/r.scale_sd,c=i===5?amber:teal;const st={mean:r.mean*k,lo:r.lo*k,hi:r.hi*k};text(s,label,62,yy-13,367,38,21,ink,i===0||i===5);line(s,[[X(st.lo),yy],[X(st.hi),yy]],c,2.6);dot(s,X(st.mean),yy,5,c,'diamond');text(s,`${pp(st.mean)} ${ci(st)}`,900,yy-13,320,38,22,c,true);});
  text(s,'Coverage stays positive in all 24 leave-one-case-out refits.',62,611,1120,29,23,teal,true);
  text(s,'R2 diagnosis may mediate the link or reflect the same latent reasoning state.',62,645,1156,25,20,muted);
 }
 // 22. Diagnostic-content ablation of the prior central finding.
 {
  const s=slide('Correct-source uptake advantage depends on fact content',note+'Only R1→R2 peer edges, no final-outcome conditioning. Known source and recipient R1 labels S/L/D, n=472 edges and 24 cases. Within case×condition panels. The paired all-minus-no-diagnosis coefficient contrast bootstraps the same cases. Mixed-tag units bearing diagnosis are excluded.','Source diagnosis correctness is not fact-level truth. Diagnosis tags include judgments and medical reasoning, not just the final-answer string.');
  text(s,'Correct minus incorrect source: R1–R2 peer uptake',62,131,1155,39,27,ink,true);
  text(s,'Same-panel comparisons: 472 edges / 24 cases. No grouping by final outcome.',62,181,1155,28,21,muted);
  const labels=[['All facts','rate'],['New to the recipient','new_rate'],['Exclude diagnosis tags','nodiag_rate'],['New + exclude diagnosis tags','new_nodiag_rate']];
  const X=forestAxis(s,377,232,422,287,-.08,.14,[-.05,0,.05,.1]);
  labels.forEach(([label,key],i)=>{const r=D.upstream.find(r=>r.measure===key&&r.adjustment==='within_panel'),y=260+i*70,c=i<2?blue:teal;text(s,label,62,y-15,303,48,22,ink);line(s,[[X(r.lo),y],[X(r.hi),y]],c,3);dot(s,X(r.mean),y,6,c,'diamond');text(s,`${pp(r.mean)} ${ci(r)} pp`,385,y+14,414,30,20,c,false,'center');});
  const z=D.targeted.diagnosis_ablation_difference;text(s,'Reduction after ablation',860,229,356,43,27,ink,true);text(s,(100*z.difference).toFixed(1)+' pp',861,302,354,67,48,blue,true);text(s,`95% CI [${(100*z.lo).toFixed(1)}, ${(100*z.hi).toFixed(1)}]`,861,388,350,37,27,muted);
  text(s,`Diagnosis-tagged units: ${(D.targeted.diagnosis_tag_share_R1*100).toFixed(1)}% of R1 output units on average.`,62,592,1156,35,26,ink,true);text(s,'The ablation changes a large part of the output composition.',62,635,1156,31,23,muted);
 }
 // 23. An observable antecedent rather than conditioning on the final outcome.
 {
  const s=slide('Prior fact overlap is associated with later uptake',note+'Panel fixed effects. Outcome is R1→R2 peer uptake rate. Controls: source and target correctness, same prior answer, prior overlap and log source fact count. Predictors below are jointly adjusted. Prior overlap is measured against recipient R1 output, before it sees source R1 output.','Observational association. Prior overlap and later uptake share source-fact denominators and may share semantic-matching errors.');
  const bx=[[62,'Source R1 output'],[463,'Recipient R1 output'],[864,'Recipient R2 output']];bx.forEach(([x,t],i)=>{box(s,x,179,350,100,blend(i===2?teal:blue,.96),rule,1);text(s,t,x+16,191,320,28,24,ink,true);text(s,i===2?'Does the fact appear again?':'The fact is already present',x+16,233,320,33,21,muted);});arrow(s,[[819,230],[852,230]],teal,2.3);
  text(s,'Jointly adjusted peer-uptake difference',62,320,1152,37,26,ink,true);
  const rows=[['Prior overlap (+10 pp)',D.mechanism.find(r=>r.key==='prior_overlap'),.1],['Same prior diagnosis (yes vs no)',D.mechanism.find(r=>r.key==='prior_same'),1],['Correct source (yes vs no)',D.upstream.find(r=>r.measure==='rate'&&r.adjustment==='prior_state_adjusted'),1]];
  const X=forestAxis(s,454,386,420,196,-.06,.14,[-.05,0,.05,.1]);
  rows.forEach(([lab,r,k],i)=>{const y=412+i*66,c=i===0?teal:blue;const st={mean:r.mean*k,lo:r.lo*k,hi:r.hi*k};text(s,lab,62,y-16,371,44,22,ink);line(s,[[X(st.lo),y],[X(st.hi),y]],c,3);dot(s,X(st.mean),y,5.5,c,'diamond');text(s,`${pp(st.mean)} ${ci(st)} pp`,918,y-12,311,40,21,c,true);});
  text(s,'No selection by final correctness. 472 peer edges, uncertainty clustered by 24 cases.',62,630,1154,31,23,muted);
 }
 // 24. Honest generalization check.
 {
  const s=slide('Fact metrics do not yet improve held-out prediction',note+'All five settings from each held-out case stay together. Fixed L2 logistic C=1; imputation and scaling fit within each fold. No tuning on held-out predictions. Observable baseline = setting, log R1 tokens, R1 answer agreement. Oracle baseline also uses R1 correct agent fraction. Fact model adds all 12 prespecified metrics. CI resamples held-out case losses, omitting training uncertainty.','Brier score: lower is better. This fixed model has no demonstrated incremental generalization; it does not rule out other fact-based models.');
  text(s,'Leave-one-case-out: all five settings held out together',62,130,1148,37,27,ink,true);
  const rows=[['Observable baseline','observable_baseline'],['+ 12 fact metrics','observable_facts'],['Oracle baseline','oracle_baseline'],['+ 12 fact metrics','oracle_facts']];const X=forestAxis(s,305,223,401,325,0,.4,[0,.1,.2,.3,.4],t=>t.toFixed(1));
  rows.forEach(([lab,k],i)=>{const r=D.cv.models[k],y=260+i*80,c=i%2?teal:ink;text(s,lab,62,y-15,234,42,23,ink);line(s,[[X(r.brier_lo),y],[X(r.brier_hi),y]],c,3);dot(s,X(r.brier),y,6,c,'diamond');text(s,r.brier.toFixed(3),718,y-15,86,40,26,c,true);});
  text(s,'Brier improvement from fact metrics',842,216,373,74,26,ink,true);
  D.cv.comparisons.forEach((r,i)=>{const y=331+i*139;text(s,r.baseline==='observable'?'Observable baseline':'Oracle baseline',842,y-23,370,33,24,ink,true);text(s,`${r.brier_improvement.toFixed(3)} [${r.lo.toFixed(3)}, ${r.hi.toFixed(3)}]`,842,y+26,385,46,25,red);});
  text(s,'Negative improvement = worse prediction',842,599,381,49,21,red);text(s,'Oracle uses R1 correctness and therefore needs the answer key.',62,606,713,53,23,muted);
 }
 // 25. Replication priorities and causal boundary.
 {
  const s=slide('Replication priorities and the causal gap',note+'No intervention has been run. Replication candidates are chosen from an exploratory audit and require independent data. A larger observational sample alone cannot resolve mediator/confounder ambiguity or gold-label/matching errors.','24 selected cases, one trace per case-setting, no clinician-reviewed truth or relevance labels for individual facts.');
  const rows=[['Best candidate','R2 evidence coverage','Positive across grading and content checks.\nNo BH significance or causal identification.',teal],['Weaker tendency','Lower R1 domain entropy','Negative direction, CI nearly reaches zero.\nMay reflect diagnosis-label concentration.',amber],['Not established','A fact-based failure detector','No held-out Brier improvement.\nCompression / novelty are grading-sensitive.',muted]];
  rows.forEach(([a,b,c,col],i)=>{const y=164+i*119;box(s,60,y,1158,104,blend(col,.97),rule,1);text(s,a,76,y+14,245,30,23,col,true);text(s,b,338,y+14,385,68,26,ink,true);text(s,c,748,y+15,455,83,22,muted);});
  text(s,'Next test: randomize evidence exposure after freezing R1',61,548,1157,37,27,ink,true);
  const steps=['Matched evidence messages\nFixed diagnosis wording','Measure R2 evidence recovery','Blindly score R3 diagnosis'];steps.forEach((t,i)=>{const x=61+i*403;box(s,x,603,353,50,blend(teal,.95),teal,1);text(s,t,x+11,607,330,44,18,ink,false,'center');if(i)arrow(s,[[x-44,628],[x-9,628]],teal,2);});
 }
}
