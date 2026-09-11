import fs from 'node:fs/promises';
import path from 'node:path';
import {createCanvas,GlobalFonts} from '@napi-rs/canvas';
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const root=path.resolve(process.env.FACTFLOW_ROOT ?? process.cwd());
const build=path.join(root,'findings/medcase24-slides/build');
const skill=process.env.PRESENTATIONS_SKILL_DIR ?? '/Users/b787pw/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.11814/skills/presentations';
process.env.RUNTIME_NODE_MODULES ??= '/Users/b787pw/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {applyPresentationChartFont,finalizePresentation}=await import(path.join(skill,'container_tools/artifact_tool_utils.mjs'));
const E=JSON.parse(await fs.readFile(path.join(build,'evidence.json'),'utf8'));
const P=Presentation.create({slideSize:{width:1280,height:720}}), font='Arial';
const C={clinical:'#287e78',laboratory:'#b27b29',imaging:'#8264b4'},N={clinical:'Clinical assessment',laboratory:'Laboratory / pathology',imaging:'Imaging'};
const conds=['shared-generic','shared-specialist','split-generic','split-specialist','split-mismatched'];
const names=['Shared / generic','Shared / specialist','Split / generic','Split / specialist','Split / mismatched'];
const cc=['#7e8994','#3d65a8','#cc913b','#14867c','#b55c86'];
const finals={Correct:'#238b59',Incorrect:'#cf4948'},ink='#213942',muted='#586d75',rule='#dce5e8';
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
function blend(hex,t=.88){const v=hex.slice(1).match(/../g).map(x=>parseInt(x,16));return '#'+v.map(x=>Math.round(x+(255-x)*t).toString(16).padStart(2,'0')).join('');}
function box(s,x,y,w,h,fill='none',stroke='none',lw=0,geometry='rect'){return s.shapes.add({geometry,position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:lw}});}
function text(s,txt,x,y,w,h,size=24,color=ink,bold=false,align='left'){
 const z=box(s,x,y,w,h);z.text=txt;z.text.style={typeface:font,fontSize:size,color,bold,alignment:align,verticalAlignment:'top',autoFit:'none',wrap:'square',insets:{top:0,bottom:0,left:0,right:0}};return z;
}
function line(s,pts,color=rule,width=1,dash=false){let xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(1,Math.max(...xs)-x),h=Math.max(1,Math.max(...ys)-y);
 return s.shapes.add({geometry:'custom',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:color,width,style:dash?'dashed':'solid'},customPaths:[{width:w,height:h,commands:pts.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0]-x,y:p[1]-y}}))}]});}
function polygon(s,pts,color){let xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]),x=Math.min(...xs),y=Math.min(...ys),w=Math.max(1,Math.max(...xs)-x),h=Math.max(1,Math.max(...ys)-y);return s.shapes.add({geometry:'custom',position:{left:x,top:y,width:w,height:h},fill:color,line:{fill:'none',width:0},customPaths:[{width:w,height:h,commands:[...pts.map((p,i)=>({[i?'lineTo':'moveTo']:{x:p[0]-x,y:p[1]-y}})),{close:{}}]}]});}
function dot(s,x,y,r,color,shape='ellipse'){return box(s,x-r,y-r,r*2,r*2,color,'none',0,shape);}
function arrow(s,pts,c=ink,w=2){line(s,pts,c,w);let b=pts.at(-1),a=pts.at(-2),dx=b[0]-a[0],dy=b[1]-a[1],l=Math.hypot(dx,dy),u=[dx/l,dy/l],v=[-u[1],u[0]],n=7+w;polygon(s,[b,[b[0]-n*u[0]+n*.45*v[0],b[1]-n*u[1]+n*.45*v[1]],[b[0]-n*u[0]-n*.45*v[0],b[1]-n*u[1]-n*.45*v[1]]],c);}
function slide(title,note,foot='') {const s=P.slides.add();s.background.fill='#FFFFFF';text(s,title,58,34,1165,70,42,ink,true);if(foot)text(s,foot,58,670,1165,40,16,muted);s.speakerNotes.textFrame.setText(note);return s;}
function legend(s,mode='condition',y=116){const pairs=mode==='role'?Object.keys(C).map(k=>[N[k],C[k]]):names.map((n,i)=>[n,cc[i]]);let w=mode==='role'?360:231;for(let i=0;i<pairs.length;i++){line(s,[[62+i*w,y+9],[87+i*w,y+9]],pairs[i][1],3);text(s,pairs[i][0],95+i*w,y-2,w-38,28,17,muted);}}
function nativeChart(s,type,cfg){for(const se of cfg.series??[]){if(se.values)se.values=se.values.map(v=>Number(v.toFixed(10)));if(se.xValues)se.xValues=se.xValues.map(v=>Number(v.toFixed(10)));}if(type==='line')cfg.lineOptions={smooth:false};const c=s.charts.add(type,cfg);applyPresentationChartFont(c,{fontFamily:font});return c;}
function gridAxis(s,x,y,w,h,xmin,xmax,ymin,ymax,xticks,yticks,xlabel='',ylabel=''){
 const fx=v=>x+(v-xmin)/(xmax-xmin)*w,fy=v=>y+h-(v-ymin)/(ymax-ymin)*h;
 for(const v of yticks){line(s,[[x,fy(v)],[x+w,fy(v)]],rule,.7);text(s,ymax<=1?`${Math.round(v*100)}%`:String(v),x-50,fy(v)-8,43,20,14,muted,false,'right');}
 line(s,[[x,y],[x,y+h],[x+w,y+h]],'#9bafb7',1);
 for(const v of xticks){text(s,typeof v==='number'?String(v):v,fx(v)-26,y+h+8,52,22,14,muted,false,'center');}
 if(xlabel)text(s,xlabel,x,y+h+34,w,28,17,muted,false,'center');if(ylabel)text(s,ylabel,x-15,y-35,w,25,18,ink,true);return {fx,fy};
}
// 1. Public example from the preferred benchmark.
{
 const s=slide('ClinicalBench: the preferred target dataset','Sources: https://github.com/WeixiangYAN/ClinicalLab and its public data_examples/data_example_en.json. The following is a paraphrased selection of the public example, not a newly invented case. ClinicalBench is the original target; it is not the source of the 24-case experimental results.','Public example only. Full ClinicalBench requires an access application and compliance with its data license.');
 text(s,'One patient, distinct professional records',60,132,950,38,28,ink,true);
 const cards=[['clinical','Middle-aged man, anonymized age\n\nTwo days of hematemesis after eating hard food. Chronic hepatitis B had remained untreated for three years. Pallor on examination.'],['laboratory','Hemoglobin 97 g/L\nPlatelets 47 × 10^9/L\nAlbumin 31.7 g/L\nProthrombin time 20.8 s\n\nThe public example contains named tests, values and reference ranges.'],['imaging','CT: cirrhosis, splenic enlargement and esophageal / gastric varices.\n\nMRI: portal hypertension.\n\nEndoscopy: variceal rupture and portal hypertensive gastropathy.']];
 cards.forEach(([k,t],i)=>{let x=60+i*400;box(s,x,191,375,330,blend(C[k]),C[k],1.5);text(s,N[k],x+16,209,342,34,25,C[k],true);text(s,t,x+16,258,342,247,22);});
 text(s,'Reference diagnosis',62,555,290,31,25,ink,true);text(s,'Rupture and bleeding of esophagogastric varices',350,556,870,37,26);
 text(s,'The record also supplies diagnostic basis and differential diagnoses.',62,609,1150,32,23,muted);
}
// 2. Actual pilot data, complete prompt.
{
 const s=slide('MedCaseReasoning: the actual pilot dataset','Source: local data/medcasereasoning/pilot24/cases.jsonl, '+E.case.id+'. Official dataset https://huggingface.co/datasets/zou-lab/MedCaseReasoning, revision 469a536, train row 423. This slide displays the full case_prompt from frozen source spans. Line breaks are adjusted for display. Reference diagnosis and reasoning never enter agent inputs.','24 selected cases with substantial evidence in all three partitions. This is a feasibility sample, not a population estimate.');
 text(s,'Original case_prompt',60,125,620,34,28,ink,true);text(s,'PMC3420544   /   216 words',820,131,400,28,20,muted,false,'right');
 const raw=E.case.evidence.map(e=>e.text).join('').replace(/\s+/g,' ').trim();const body=text(s,raw,62,184,1154,386,24);
 // Use the rendered line breaks and exact font advances to mark source partitions.
 GlobalFonts.registerFromPath('/System/Library/Fonts/Supplemental/Arial.ttf','CaseArial');
 const ctx=createCanvas(1,1).getContext('2d');ctx.font='24px CaseArial';
 const layout=JSON.parse(await (await s.export({format:'layout'})).text());
 const lines=layout.elements.find(e=>e.text===raw).textLayout.lines;
 let offset=0;const spans=E.case.evidence.map(e=>{const t=e.text.replace(/\s+/g,' ').trim(),start=raw.indexOf(t,offset);if(start<0)throw new Error('Case span missing');offset=start+t.length;return {start,end:offset,category:e.category};});
 offset=0;for(const [i,l] of lines.entries()){
  const start=raw.indexOf(l.text,offset);if(start<0)throw new Error('Rendered line missing');offset=start+l.text.length;
  for(const sp of spans){const a=Math.max(start,sp.start),b=Math.min(offset,sp.end);if(a>=b)continue;
   const x=62+ctx.measureText(raw.slice(start,a)).width,w=ctx.measureText(raw.slice(a,b)).width;
   box(s,x-1,187+i*28.8,w+2,27.6,C[sp.category]+'/14',C[sp.category]+'/32',.6);
  }
 }
 body.bringToFront();
 for(const [i,k] of Object.keys(C).entries()){const x=470+i*247;box(s,x,162,17,13,C[k]+'/14',C[k]+'/32',.7);text(s,N[k],x+24,159,235,23,16,muted);}

 line(s,[[62,589],[1218,589]],rule,1);text(s,'Reference held out from agents',62,614,370,32,21,muted);text(s,'Chronic recurrent multifocal osteomyelitis',450,610,765,42,27,ink,true);
}
// 3. Exact source spans, same professional colors.
{
 const s=slide('The same case, partitioned by evidence source','Source: '+E.case.id+', source-spans-v1. Whole original spans form disjoint partitions. Shared metadata gives age and sex. Initial evidence retains source content, no added reports. Original prompt can be reconstructed in source order. Role assignments A clinical, B laboratory/pathology, C imaging for this case.','The partitions preserve the original statements. Every agent receives the same patient metadata and a joint diagnostic task.');
 text(s,'Common metadata: 13-year-old female',60,129,1120,38,27,ink,true);
 Object.keys(C).forEach((k,i)=>{const x=60+i*400;box(s,x,192,375,466,blend(C[k]),C[k],1.5);text(s,String.fromCharCode(65+i)+'  '+N[k],x+15,208,345,40,24,C[k],true);const body=E.case.evidence.filter(e=>e.category===k).map(e=>e.text.trim()).join('\n\n').replace(/\n\n/g,'\n');text(s,body,x+15,250,345,406,19);});
}
// 4. Controlled runs.
{
 const s=slide('Five conditions isolate roles and information','Sources: configs/pilots/medcase24/*.yaml and docs/medcase24-pilot.md. Three synchronous rounds, full connectivity. Seat mapping counterbalanced over six permutations. Mismatch uses derangements. 24 independent cases, 120 case-condition traces, 1080 outputs. Inference model DeepSeek v4-flash.','Same cases, model and communication rules. Specialist means a source-related function, not an organ-specific medical department.');
 const rows=[['Setting','Initial evidence','Role prompts'],['Shared / generic','All evidence to everyone','Three generic agents'],['Shared / specialist','All evidence to everyone','Clinical, lab/pathology, imaging'],['Split / generic','One partition per agent','Three generic agents'],['Split / specialist','One partition per agent','Matching specialists'],['Split / mismatched','One partition per agent','All specialist roles mismatched']];
 const tb=s.tables.add({rows:6,columns:3,left:60,top:160,width:1160,height:315,values:rows,columnWidths:[350,350,460]});
 for(let i=0;i<6;i++)for(let j=0;j<3;j++){let cell=tb.getCell(i,j);cell.text.style={fontSize:23,typeface:font,color:i?ink:'#FFFFFF',bold:i===0};cell.fill=i===0?ink:(i%2?'#f3f7f8':'#ffffff');}
 tb.borders.assign({fill:'#FFFFFF',width:2});
 text(s,'24 cases × 5 settings = 120 traces',60,519,1100,47,34,ink,true);
 text(s,'3 agents   /   3 rounds   /   Full synchronous communication\nR2 and R3 receive both peers’ preceding output. Each agent answers every round.',60,579,1160,68,23);
}
// Experimental conditions: role nodes and initial-evidence satellites.
{
 const s=slide('Five experimental settings',
  'Sources: configs/pilots/medcase24/*.yaml; docs/medcase24-pilot.md. Each graph shows three agents with full synchronous peer communication. Large nodes encode role prompts; dark satellite dots encode initial evidence partitions. Shared gives all three partitions to every agent; split gives one. The mismatched example uses a cyclic derangement; actual seats and derangements are counterbalanced across cases. Satellites describe initial evidence only, before peer communication.',
  'All graphs use full synchronous communication. Small dots show initial evidence; seat positions are illustrative.');
 const keys=Object.keys(C),dark=Object.fromEntries(keys.map(k=>[k,'#'+C[k].slice(1).match(/../g).map(v=>Math.round(parseInt(v,16)*.72).toString(16).padStart(2,'0')).join('')]));
 text(s,'Large circles: role     Small solid dots: initial evidence',60,116,650,30,21,muted);
 for(const [i,k] of keys.entries()){const x=740+i*166;dot(s,x,130,6,dark[k]);text(s,['Clinical','Lab / pathology','Imaging'][i],x+14,116,153,28,18,C[k],true);}
 box(s,58,164,1164,233,'#f1f5f8');
 box(s,58,414,1164,236,'#f3f7f4');
 line(s,[[60,405],[1220,405]],'#b8c6cc',1.2);
 text(s,'SHARED',78,251,158,38,27,ink,true);text(s,'All partitions\nto every agent',78,294,162,63,20,muted);
 text(s,'SPLIT',78,502,150,38,27,ink,true);text(s,'One partition\nper agent',78,544,150,64,20,muted);
 function setting(cx,top,title,generic,shared,mismatch=false){
  text(s,title,cx-151,top,302,34,25,ink,true,'center');
  const pos=[[cx,top+76],[cx-82,top+167],[cx+82,top+167]],r=33;
  // Separate curved paths for both directed edges; arrow tips remain outside nodes.
  for(let a=0;a<3;a++)for(let b=0;b<3;b++){if(a===b)continue;
   const p=pos[a],q=pos[b],dx=q[0]-p[0],dy=q[1]-p[1],d=Math.hypot(dx,dy),ctrl=[(p[0]+q[0])/2-dy/d*22,(p[1]+q[1])/2+dx/d*22];
   const at=(p,gap)=>{const dx=ctrl[0]-p[0],dy=ctrl[1]-p[1],d=Math.hypot(dx,dy);return [p[0]+dx/d*(r+gap),p[1]+dy/d*(r+gap)];};
   const start=at(p,2),end=at(q,6),pts=Array.from({length:33},(_,i)=>{const t=i/32;return [(1-t)**2*start[0]+2*(1-t)*t*ctrl[0]+t*t*end[0],(1-t)**2*start[1]+2*(1-t)*t*ctrl[1]+t*t*end[1]];});
   arrow(s,pts,'#657780',1.3);
  }
  for(let i=0;i<3;i++){
   const [x,y]=pos[i],k=keys[i],col=generic?'#292f34':C[k];
   box(s,x-r,y-r,r*2,r*2,generic?'#d8dce0':blend(C[k],.82),col,1.8,'ellipse');
   const label=generic?'Generic':i===0?'Clinical':i===1?'Lab /\npath':'Imaging';
   text(s,label,x-31,y-(i===1&&!generic?18:10),62,i===1&&!generic?39:26,i===1&&!generic?13:14,col,true,'center');
   const side=i===1?-1:1,sx=x+side*52;
   const evidence=shared?keys:[keys[mismatch?(i+1)%3:i]];
   if(shared){[[sx,y-10],[sx-10,y+8],[sx+10,y+8]].forEach(([xx,yy],j)=>dot(s,xx,yy,7,dark[evidence[j]]));}
   else dot(s,sx,y,8,dark[evidence[0]]);
  }
 }
 setting(478,178,'Generic',true,true);
 setting(985,178,'Specialist',false,true);
 setting(385,427,'Generic',true,false);
 setting(725,427,'Matching specialists',false,false);
 setting(1065,427,'Mismatched specialists',false,false,true);
}
// 5. Editable pipeline diagram with first-stage negative labels.
{
 const s=slide('Atomic facts and relation labels','Sources: configs/extraction/minimax-m3-speed-v4.yaml; docs/server-matching.md. Actual extraction MiniMax M3 with thinking disabled, candidate-only atomization. BGE and lexical blocker 0.62 top-12; Qwen3-14B directional YES/NO margins; threshold 5.28. Blocker negatives are UNRELATED labels, equal in status to NLI negatives.','Each initial source and each output is processed separately. The extractor never receives a bundled prior conversation or the answer key.');
 const blocks=[['One text','Source or output'],['MiniMax M3','Extract atomic facts\nThinking disabled'],['Candidate refinement','Split selected compounds\nPreserve exact quotes']];
 let nodes=[];blocks.forEach((b,i)=>{let x=60+i*404;let n=box(s,x,170,354,130,'#f0f5f6','#b3c4cb',1.3);text(s,b[0],x+18,188,318,31,26,ink,true);text(s,b[1],x+18,232,318,55,22);nodes.push(n);if(i)s.shapes.connect(nodes[i-1],n,{fromSide:'right',toSide:'left',kind:'straight',line:{fill:ink,width:2},tail:{type:'triangle'}});});
 text(s,'Fact ID + text + exact quote / span + content domains + existing annotations',61,334,1150,40,24,ink,true);
 let b=box(s,60,412,300,127,'#f0f5f6','#b3c4cb',1.3);text(s,'Lexical + BGE blocker',78,432,266,35,25,ink,true);text(s,'First inexpensive label',78,477,260,35,21);
 let n=box(s,490,412,310,127,'#f0f5f6','#b3c4cb',1.3);text(s,'Local Qwen3-14B',508,432,278,35,25,ink,true);text(s,'Both entailment directions',508,477,278,38,21);
 s.shapes.connect(b,n,{fromSide:'right',toSide:'left',kind:'straight',line:{fill:ink,width:2},tail:{type:'triangle'}});text(s,'Candidate pairs',360,448,130,52,17,muted,false,'center');
 text(s,'Unrelated\nA entails B\nB entails A\nEquivalent',913,400,290,143,25,ink,true);arrow(s,[[800,471],[889,471]],ink,2);
 arrow(s,[[210,539],[210,609],[890,609]],muted,2);text(s,'Blocker negatives',295,578,590,28,22,muted);text(s,'UNRELATED',913,595,290,40,25,ink,true);
}
// 6. Viewer example and overall measured graph.
{
 const s=slide('From located facts to information flow','Sources: frozen viewer '+E.case.id+' / split-specialist. Selected source atom 1295 in B|1, equivalent to 380 in A|2 (margins 17.0,22.875) and 1082 in C|2 (18.5,19.75). Both recipients saw B|1. Right graph: all-output direct-equivalence source uptake, recipient edges averaged within source, rounds and conditions within case, then 24 case means. Includes all five settings.','A link requires visible source output and a matching fact. It is an opportunity for transmission, not proof of copying. No parallel R1 links.');
 text(s,'Located fact in one trace',60,132,690,34,27,ink,true);text(s,'Mean uptake across the study',820,132,390,62,25,ink,true);
 const xs=[70,294,518],keys=Object.keys(C),seats=['A','B','C'];let selected={};
 for(let rd of [1,2]){text(s,'R'+rd,60,rd===1?183:406,650,26,22,muted,true);for(let i=0;i<3;i++){let y=rd===1?220:443;box(s,xs[i],y,203,141,blend(C[keys[i]]),C[keys[i]],1);text(s,seats[i]+'  '+(i===0?'Clinical':i===1?'Lab / pathology':'Imaging'),xs[i]+10,y+12,183,30,20,C[keys[i]],true);
 let str=rd===1?(i===0?'Spine pain and knee arthritis.':i===1?'“negative cultures and PCR”':'Multiple vertebral lesions on MRI.'):(i===0?'“with negative cultures”':i===1?'Integrates laboratory and peer evidence.':'“negative cultures”');text(s,str,xs[i]+10,y+54,183,69,20);
 if(rd===1&&i===1||rd===2&&i!==1){let h=box(s,xs[i]+8,y+51,187,75,'none',C.laboratory,2.5);selected[seats[i]+'|'+rd]=h;}
 }}
 for(let x of [171,619])arrow(s,[[396,367],[x,436]],C.laboratory,2.5);
 text(s,'Selected proposition: biopsy cultures are negative',70,606,665,35,22,C.laboratory,true);
 const pos={clinical:[1008,270],laboratory:[864,493],imaging:[1150,493]},radius=65;
 for(const a of keys)for(const b of keys){if(a===b)continue;
  const p=pos[a],q=pos[b],dx=q[0]-p[0],dy=q[1]-p[1],d=Math.hypot(dx,dy);
  const ctrl=[(p[0]+q[0])/2-dy/d*72,(p[1]+q[1])/2+dx/d*72];
  const outside=(center,r)=>{const dx=ctrl[0]-center[0],dy=ctrl[1]-center[1],d=Math.hypot(dx,dy);return [center[0]+dx/d*r,center[1]+dy/d*r];};
  const start=outside(p,radius+3),end=outside(q,radius+7);
  const curve=t=>[(1-t)**2*start[0]+2*(1-t)*t*ctrl[0]+t*t*end[0],(1-t)**2*start[1]+2*(1-t)*t*ctrl[1]+t*t*end[1]];
  const v=E.flow.find(e=>e.source===a&&e.target===b).rate;
  arrow(s,Array.from({length:65},(_,i)=>curve(i/64)),C[a],1+v*10);
  const mid=curve(.5);box(s,mid[0]-32,mid[1]-14,64,28,'#FFFFFF');text(s,(100*v).toFixed(1)+'%',mid[0]-31,mid[1]-11,62,25,18,C[a],true,'center');
 }
 for(const k of keys){let [x,y]=pos[k],self=E.flow.find(e=>e.source===k&&e.target===k).rate;box(s,x-radius,y-radius,2*radius,2*radius,blend(C[k]),C[k],2,'ellipse');text(s,k==='laboratory'?'Lab / path':k==='clinical'?'Clinical':'Imaging',x-61,y-24,122,28,22,C[k],true,'center');text(s,'Self '+(100*self).toFixed(1)+'%',x-61,y+8,122,24,18,ink,false,'center');}
 text(s,'Arrow width = source-fact uptake rate',817,619,402,26,19,muted);
}
// 7. Outcome context, native editable line charts.
{
 const s=slide('Diagnostic outcome depends on the grading rule','Source: findings/medcase24-study/summary.json accuracy. Left: literal-system majority, exact normalized string equality. Right: semantic-system majority, accepted S+L name relation to reference. S means same disease/specificity, L a definite diagnostic hierarchy. This is name-level grading, not clinical fact truth. Shading uses the saved 2,000-resample case-bootstrap pointwise 95% intervals. CI polygons are editable overlays behind transparent native charts, so update them with the chart if data changes.','24 cases per setting. The two panels use the saved literal and semantic vote definitions. Shading: pointwise 95% case-bootstrap CI (2,000 resamples).');legend(s);
 for(const [j,level,key,title] of [[0,'literal_system','exact','Exact diagnosis name'],[1,'semantic_system','fuzzy_inclusive','Same disease or accepted hierarchy']]){
 text(s,title,70+j*610,169,535,50,27,ink,true);
 // Chart plot coordinates are fixed by the original 560 x 385 chart geometry.
 const xs=[203.667,365.667,527.667].map(x=>x+j*610),Y=v=>574-337*v;
 for(const [i,c] of conds.entries()){
  const st=[1,2,3].map(rd=>E.accuracy.find(r=>r.condition===c&&r.round===rd&&r.level===level).metrics[key]);
  if(st.some(r=>r.n!==24||r.lo>r.mean||r.hi<r.mean))throw new Error('Invalid accuracy interval');
  polygon(s,[...st.map((r,k)=>[xs[k],Y(r.lo)]),...st.map((r,k)=>[xs[k],Y(r.hi)]).reverse()],cc[i]+'/12');
 }
 nativeChart(s,'line',{chartFill:'none',plotAreaFill:'none',position:{left:60+j*610,top:228,width:560,height:385},categories:['R1','R2','R3'],series:conds.map((c,i)=>({name:names[i],values:[1,2,3].map(rd=>E.accuracy.find(r=>r.condition===c&&r.round===rd&&r.level===level).metrics[key].mean),line:{fill:cc[i],width:3},marker:{symbol:'circle',size:5}})),hasLegend:false,yAxis:{min:0,max:1,majorUnit:.25,numberFormatCode:'0%',textStyle:{fontSize:18},majorGridlines:{fill:rule,width:1}},xAxis:{textStyle:{fontSize:22},majorGridlines:null}});
 }
}
// Native editable scatter geometry replicates the PDF point data.
function profile(metric,key,title){
 const data=E.figures[key],pct=metric==='output_own';const s=slide(title,'Source: findings/medcase24-figures/figure-data.json '+key+'. Same 1080 case-agent observations and case-bootstrap intervals as the PDF. Fractional original-domain labels, within-output equivalence units, direct-equivalence uptake. Domain assignments follow prompts in mismatch.','Points: case-agent ratios. Large markers: profession means and black case means. Bars: 95% case-bootstrap CI. Missing denominators stay missing.');legend(s,'role');
 const x0=269,pw=237,gap=87,y0=222,step=77,lo=pct?0:-1,hi=1;
 for(let rd=1;rd<=3;rd++){
  let x=x0+(rd-1)*(pw+gap);const X=v=>x+(v-lo)/(hi-lo)*pw;text(s,'R'+rd,x,170,pw,31,26,ink,true,'center');
  for(let [a,b,tint] of [[0,1,'#edf3f8'],[2,3,'#edf6f2']])box(s,x,y0+a*step-23,pw,(b-a+1)*step,tint);
  const ticks=pct?[0,.25,.5,.75,1]:[-1,-.5,0,.5,1];for(let v of ticks){line(s,[[X(v),y0-23],[X(v),y0+4*step+55]],v===0?'#a5b7bd':'#e5ecef',.7,v===0);text(s,`${Math.round(v*100)}%`,X(v)-25,600,50,22,14,muted,false,'center');}
  for(let ci=0;ci<5;ci++){
   let y=y0+ci*step;if(rd===1)text(s,names[ci],62,y-2,192,45,19,ink);
   let points=data.points.filter(r=>r.condition===conds[ci]&&r.round===rd);for(let [i,r] of points.entries()){if(r[metric]==null)continue;let jitter=(((i*37+rd*13)%73)/72-.5)*26;dot(s,X(r[metric]),y+jitter,2.6,blend(C[r.field],.35));}
   for(let [j,k] of [...Object.keys(C),'all'].entries()){
    const st=data.summary.find(r=>r.condition===conds[ci]&&r.round===rd&&r.field===k), yy=y+23+j*6,col=C[k]??ink;
    if(st.mean!=null){if(st.lo!=null)line(s,[[X(st.lo),yy],[X(st.hi),yy]],col,1.6);dot(s,X(st.mean),yy,3.9,col,ci%2===0&&ci!==4?'ellipse':ci===4?'triangle':'diamond');}
    if(ci<4){let next=data.summary.find(r=>r.condition===conds[ci+1]&&r.round===rd&&r.field===k);if(st.mean!=null&&next.mean!=null)line(s,[[X(st.mean),yy],[X(next.mean),yy+step]],blend(col,.45),1,ci===1||ci===3);}
    if(k==='all'){let value=st.mean==null?'NA':(pct?`${(100*st.mean).toFixed(1)}%`:`${st.mean>=0?'+':''}${(100*st.mean).toFixed(1)} pp`);text(s,value,x+pw+3,y-1,64,20,13,ink,false,'right');let n=points.filter(r=>r[metric]!=null).length;if(n<72)text(s,`n=${n}/72`,x+pw+3,y+16,64,20,12,muted,false,'right');}
   }
  }
  text(s,pct?'Own-profession output share':'Own - other uptake rate',x,633,pw,29,18,muted,false,'center');
 }
 return s;
}
profile('uptake_prime','01_uptake_prime','Professional selectivity in fact uptake');
profile('output_own','output_own','Professional preference in output content');
// 10. Same token-clock panels as the revised PDF.
{
 const s=slide('Shared information produces fewer cumulative facts','Source: figure-data.json token-R0, token-R1, token-R2, token-R3, token-R-1. Same numerical curves and case-bootstrap bands as the revised token-clock PDF. Tokenizer BAAI/bge-base-en-v1.5; quote-end positioning. The round mean averages R1/R2/R3 within case without cross-round merging.','Left merges output facts across rounds. Right resets each round and averages at a common within-round token budget. No hidden reasoning tokens.');legend(s);text(s,'Distinct output facts (equivalence components)',60,161,900,27,19,muted);
 const panels=[[0,95,235,485,360,'Cumulative R1-R3'],[1,686,225,215,140,'R1'],[2,997,225,215,140,'R2'],[3,686,472,215,140,'R3'],[-1,997,472,215,140,'Round mean']];
 for(const [rd,x,y,w,h,title] of panels){let rs=E.figures['token-R'+rd],xmax=rs[0].tokens.at(-1),ymax=rd===0?140:60;const {fx,fy}=gridAxis(s,x,y,w,h,0,xmax,0,ymax,[0,Math.floor(xmax/200)*100,Math.round(xmax)],[0,ymax/2,ymax],'Output tokens',title);
  for(let [i,r] of rs.entries()){
   let band=[...r.tokens.map((t,j)=>[fx(t),fy(r.lo[j])]),...r.tokens.map((t,j)=>[fx(t),fy(r.hi[j])]).reverse()];polygon(s,band,blend(cc[i],.91));
  }
  for(let [i,r] of rs.entries())line(s,r.tokens.map((t,j)=>[fx(t),fy(r.mean[j])]),cc[i],rd===0?2.8:2);
 }
}
// 11. A metric and an explicit, labeled algebraic illustration.
{
 const s=slide('Cross-round merging has a direct trace-level measure','Source: scripts/study_report/merge_levels.py and findings/medcase24-merging/analysis.json. C is calculated per trace, then summarized over cases. These are definitions on the saved equivalence graph.','Compression counts graph merging. Direct recurrence checks whether the pattern survives without cross-round transitive closure.');
 text(s,'Cross-round compression',60,141,600,39,29,ink,true);text(s,'C = 1 − pooled fact count / sum of round fact counts',60,205,1150,47,31,ink,true);
 text(s,'Higher C means more of the separately counted facts merge when rounds are pooled.',60,265,1150,65,25);
 text(s,'Decomposition and a direct-match check',60,362,1140,34,27,ink,true);
 text(s,'Repeated presence\nAn equivalence cluster appears in multiple rounds.',60,426,346,105,24);
 text(s,'Bridge merging\nCross-round links join components that were separate within a round.',467,426,350,140,24);
 text(s,'Direct recurrence D\nFraction of units with a direct equivalent in another round, averaged over round pairs.',883,426,332,153,24);
 line(s,[[420,421],[420,595]],rule,1);line(s,[[850,421],[850,595]],rule,1);
 text(s,'C = repeated-presence share + bridge share',60,606,1150,40,29,ink,true);
}
// 12. Editable native bar chart and exact contrasts.
{
 const s=slide('Information splitting reduces cross-round merging','Source: merging/analysis.json. Left stacked values are means of per-case repeated-presence and bridge shares and sum exactly to compression. Right: shared minus split case-paired contrasts with 2000-draw 95% bootstrap CI. Six newly examined contrasts share BH q; all six p,q<.001, exploratory pilot.','Independent n = 24 cases. The pattern also holds on raw atom IDs without any clustering. Lower merging does not establish better clinical reasoning.');
 text(s,'Compression level by setting',60,142,650,38,27,ink,true);
 nativeChart(s,'bar',{position:{left:46,top:206,width:716,height:416},categories:[...names].reverse(),series:[{name:'Repeated presence',values:[...E.merging.conditions].reverse().map(c=>c.repeat_share.mean),valuesFormatCode:'0.0%',fill:'#3d65a8'},{name:'Bridge merging',values:[...E.merging.conditions].reverse().map(c=>c.bridge_share.mean),valuesFormatCode:'0.0%',fill:'#9bb9cc'}],barOptions:{direction:'bar',grouping:'stacked',overlap:100,gapWidth:60},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:19}},xAxis:{min:0,max:.6,numberFormatCode:'0%',textStyle:{fontSize:18},majorGridlines:{fill:rule,width:1}},yAxis:{min:0,max:.6,numberFormatCode:'0%',textStyle:{fontSize:19}},dataLabels:{showValue:false},});
 E.merging.conditions.forEach((c,i)=>{const y=248+i*67.5;let start=219;for(const key of ['repeat_share','bridge_share']){let width=c[key].mean/.6*510;text(s,(100*c[key].mean).toFixed(1)+'%',start+width/2-38,y-12,76,25,18,'#FFFFFF',true,'center');start+=width;}});
 text(s,'Shared − split',820,145,380,37,28,ink,true);
 const metrics=[['compression','Compression'],['direct_coverage','Direct recurrence']];let y=213;
 for(let [m,label] of metrics){text(s,label,820,y,390,32,25,ink,true);y+=49;for(let role of ['generic','specialist']){let r=E.merging.contrasts.find(z=>z.left==='shared-'+role&&z.right==='split-'+role&&z.metric===m);text(s,role==='generic'?'Generic':'Specialist',820,y,180,29,22,muted);text(s,`+${(100*r.mean).toFixed(1)} pp`,1000,y-4,215,37,30,ink,true,'right');text(s,`95% CI [${(100*r.lo).toFixed(1)}, ${(100*r.hi).toFixed(1)}]`,820,y+37,392,28,21,muted,false,'right');y+=86;}y+=13;}
}
// 13. Recurrence persists through the last transition.
{
 const s=slide('Shared conditions remain more repetitive after exchange','Source: merging/analysis.json round_pairs. D uses direct identity/equivalence links between within-round units and averages matched fractions from both sides. No cross-round closure. Threshold sensitivity reuses stored margins and does not rescore blocker negatives.','The gap narrows after discussion, but remains at R2/R3. This does not prove whether recurrence reflects copying or independent reuse of shared evidence.');legend(s);
 text(s,'Direct recurrence D',62,164,760,32,25,ink,true);
 nativeChart(s,'line',{position:{left:60,top:206,width:775,height:420},categories:['R1 / R2','R1 / R3','R2 / R3'],series:conds.map((c,i)=>({name:names[i],values:[[1,2],[1,3],[2,3]].map(([a,b])=>E.merging.round_pairs.find(r=>r.condition===c&&r.from_round===a&&r.to_round===b).direct_coverage.mean),line:{fill:cc[i],width:3},marker:{symbol:'circle',size:7}})),hasLegend:false,yAxis:{min:0,max:.8,majorUnit:.2,numberFormatCode:'0%',textStyle:{fontSize:19},majorGridlines:{fill:rule,width:1}},xAxis:{textStyle:{fontSize:23}}});
 text(s,'Threshold sensitivity',891,211,320,60,27,ink,true);text(s,'NLI margins 4.5–6.0',891,289,320,42,24);
 text(s,'Shared − split',891,354,320,32,24,muted);text(s,'11.6–13.8 pp',891,403,320,48,35,ink,true);text(s,'compression gap',891,452,320,33,23,muted);text(s,'14.7–18.2 pp',891,510,320,48,35,ink,true);text(s,'direct-recurrence gap',891,560,320,57,23,muted);
}
function quantile(a,q){a=[...a].sort((x,y)=>x-y);let p=(a.length-1)*q,i=Math.floor(p);return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(p-i);}
function sourceBoxes(kind,title){
 const s=slide(title,'Source: figure-data.json '+kind+'-pooled-boxplot and pooled-inference. Same boxplot data as the PDF. Boxes contain case means, not edge observations. Correct S+L vs incorrect D. Rows pool R1-R2 and R2-R3. Final labels denote R3 system outcomes. All-final column repeats the two colored strata. Paired inference uses panels with both groups before case averaging.','Boxes: case means, median and IQR. Diamonds / bars: mean / 95% CI. p: case sign-flip. q: BH across 8 tests. Δ: '+(kind==='correctness'?'correct - incorrect':'minority - majority')+'');
 for(let [j,k] of ['Correct','Incorrect'].entries()){dot(s,420+j*265,124,5,finals[k],'rect');text(s,'Final '+k.toLowerCase(),437+j*265,111,240,31,23,finals[k]);}
 const records=E.figures[kind+'-pooled-boxplot'],labels=kind==='correctness'?['Correct','Incorrect']:['Majority','Minority'];
 for(let [ri,receiver] of ['self','peers'].entries())for(let [ci,outcome] of ['All','Correct','Incorrect'].entries()){
  let x=91+ci*410,y=ri===0?219:466,w=323,h=116;const X=g=>x+75+labels.indexOf(g)*170,Y=v=>y+h-v*h;
  text(s,(ri===0?'Self: ':'Peers: ')+(outcome==='All'?'all finals':'final '+outcome.toLowerCase()),x-8,ri===0?168:415,w+15,35,24,finals[outcome]??ink,true,'center');

  if(outcome!=='All')box(s,x,y,w,h,blend(finals[outcome],.97));
  for(let v of [0,.5,1]){line(s,[[x,Y(v)],[x+w,Y(v)]],rule,1);if(ci===0)text(s,`${v*100}%`,x-52,Y(v)-8,47,20,14,muted,false,'right');}
  for(const r of records.filter(r=>r.receiver===receiver&&r.panel===outcome)){
   let vals=Object.values(r.case_values),st=r.stat,xx=X(r.group)+(outcome==='All'?(r.final==='Correct'?-33:33):0),col=finals[r.final];
   if(!vals.length)continue;let q1=quantile(vals,.25),q3=quantile(vals,.75),med=quantile(vals,.5),iqr=q3-q1,low=Math.min(...vals.filter(v=>v>=q1-1.5*iqr)),high=Math.max(...vals.filter(v=>v<=q3+1.5*iqr));
   line(s,[[xx,Y(low)],[xx,Y(high)]],col,1.3);line(s,[[xx-10,Y(low)],[xx+10,Y(low)]],col,1.3);line(s,[[xx-10,Y(high)],[xx+10,Y(high)]],col,1.3);box(s,xx-22,Y(q3),44,Math.max(1,Y(q1)-Y(q3)),blend(col,.78),col,1.4);line(s,[[xx-22,Y(med)],[xx+22,Y(med)]],col,2);if(st.lo!=null)line(s,[[xx,Y(st.lo)],[xx,Y(st.hi)]],col,2);dot(s,xx,Y(st.mean),4,col,'diamond');
   vals.filter(v=>v<low||v>high).forEach(v=>dot(s,xx,Y(v),2,col));text(s,'n='+st.n,xx-29,y+4,58,20,14,col,false,'center');
  }
  labels.forEach(g=>text(s,g,X(g)-72,y+h+9,144,28,18,ink,false,'center'));
  if(outcome==='All')text(s,'Both final-outcome strata',x,y+h+43,w,25,16,muted,false,'center');else{let t=E.figures['pooled-inference'].find(t=>t.kind===kind&&t.receiver===receiver&&t.final===outcome),st=t.effect;let pp=v=>v<.001?'<.001':'='+v.toFixed(3);text(s,`Δ ${(100*st.mean).toFixed(1)} pp [${(100*st.lo).toFixed(1)}, ${(100*st.hi).toFixed(1)}]\nn=${st.n}, p${pp(t.p)}, q${pp(t.q)}`,x-7,y+h+42,w+14,47,15,finals[outcome],false,'center');}
 }
 return s;
}
sourceBoxes('correctness','Correct sources are favored mainly in successful traces');
sourceBoxes('majority','Minority sources tend to receive less peer uptake');
// 16. One representative factorial heatmap page.
{
 const s=slide('Correctness and majority status jointly stratify uptake','Source: figure-data.json factorial-pooled-peers. Strict 2:1 panels, known source correctness, all final outcomes. Source rates -> panels -> rounds -> condition -> case. Overall cells give equal weight to available setting-cell means, with k/5 coverage. Empty cells remain absent. These are marginal descriptive cell means, not causal contrasts.','Peer uptake, pooled transitions. Each cell shows mean and independent case n. Sparse correct-minority cells limit interpretation.');
 for(let i=0;i<6;i++){
  let x=126+(i%3)*403,y=205+Math.floor(i/3)*232;const cond=i<5?conds[i]:'average';text(s,i<5?names[i]:'Equal mean of available settings',x-63,y-47,366,39,22,ink,true,'center');
  for(let a=0;a<2;a++)for(let b=0;b<2;b++){
   let r=E.figures['factorial-pooled-peers'].find(r=>r.condition===cond&&r.truth===['Correct','Incorrect'][a]&&r.status===['Majority','Minority'][b]);let v=r.mean,fill=v==null?'#f7f8f9':blend('#176986',1-v*1.35);box(s,x+b*127,y+a*72,126,71,fill,'#ffffff',1);text(s,v==null?'NA':`${(100*v).toFixed(1)}%\nn=${r.n}`+(i===5?`, ${r.settings}/5`:''),x+b*127+3,y+a*72+16,120,47,18,ink,false,'center');
  }
  ['Correct','Incorrect'].forEach((v,j)=>text(s,v,x-84,y+j*72+25,78,27,16,muted,false,'right'));['Majority','Minority'].forEach((v,j)=>text(s,v,x+j*127,y+153,127,24,17,muted,false,'center'));
 }
}
// 17. Novelty hypothesis does not gain support.
{
 const s=slide('The role effect is not clearly larger for new facts','Source: figure-data.json novel-interaction-output_own. New fact = no identity/direct equivalence match to any previous-round output. Differences pair specialist-generic within case, then subtract old-fact effect from new-fact effect. Initial-source exclusion is a separate sensitivity view.','All four 95% case-bootstrap intervals cross zero. The current pilot does not establish a stronger role effect on new output facts.');
 text(s,'Interaction = role effect among new facts − role effect among old facts',60,130,1155,66,27,ink,true);
 for(let [j,rd] of [2,3].entries()){
  let x=195+j*581,y=257,w=415,h=265;const X=v=>x+(v+.15)/.3*w;text(s,'R'+rd,x,211,w,35,28,ink,true,'center');line(s,[[X(0),y],[X(0),y+h]],'#b1c1c8',1.5,true);
  for(let [i,info] of ['shared','split'].entries()){let yy=y+58+i*148,r=E.figures['novel-interaction-output_own'].find(r=>r.info===info&&r.round===rd);text(s,info==='shared'?'Shared':'Split',x-112,yy-12,100,30,24,ink,false,'right');line(s,[[X(r.lo),yy],[X(r.hi),yy]],'#3d65a8',3);dot(s,X(r.mean),yy,6,'#3d65a8','diamond');text(s,`${(100*r.mean).toFixed(1)} pp [${(100*r.lo).toFixed(1)}, ${(100*r.hi).toFixed(1)}]`,x,yy+27,w,32,22,muted,false,'center');}
  for(let v of [-.15,0,.15])text(s,`${v*100} pp`,X(v)-38,y+h+17,76,27,20,muted,false,'center');
 }
}
// 18. Concise supported interpretation and limits.
{
 const s=slide('What the pilot establishes','Sources: merging/README.md; medcase24-figures/README.md. All findings describe 24 selected MedCaseReasoning cases with one trace per case-condition. No atomic-fact ground truth. Mechanism proposals remain hypotheses.','The next validation should preserve paired cases and fixed prompts while auditing actual repeated facts and expanding independent cases.');
 text(s,'Information allocation changes redundancy',60,153,1120,40,31,ink,true);
 text(s,'Shared inputs increase compression by 12–13 percentage points. Direct recurrence and raw-atom checks show the same pattern.',60,208,1138,87,27);
 text(s,'Role prompts change content preference',60,339,1120,42,31,ink,true);
 text(s,'Professional uptake preferences differ even when final accuracy looks similar. Lower merging is not automatically a better outcome.',60,394,1138,89,27);
 text(s,'The mechanism remains open',60,523,1120,40,31,ink,true);
 text(s,'Recurrence can reflect copying or independent reuse. More distinct output can reflect useful complementarity, unresolved disagreement or unsupported claims.',60,577,1138,76,26);
}
const outcome=JSON.parse(await fs.readFile(path.join(root,'findings/medcase24-fact-outcome/analysis.json'),'utf8'));
const {addOutcomeSlides}=await import(path.join(root,'scripts/study_report/outcome_slides.mjs'));
addOutcomeSlides({D:outcome,slide,text,box,line,arrow,dot,ink,muted,rule,blend});
await fs.mkdir(path.join(build,'preview'),{recursive:true});
const candidate=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(P)).save(candidate);
console.log('Draft saved',P.slides.items.length);
for(let i=0;i<P.slides.items.length;i++){
 const s=P.slides.items[i];const png=await P.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,'preview',String(i+1).padStart(2,'0')+'.png'),new Uint8Array(await png.arrayBuffer()));
 const layout=await s.export({format:'layout'});await fs.writeFile(path.join(build,'preview',String(i+1).padStart(2,'0')+'.layout.json'),await layout.text());console.log('Rendered',i+1);
}
await fs.mkdir(path.join(root,'findings/medcase24-validation'),{recursive:true});
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:process.env.FINAL_PPTX ?? path.join(root,'findings/medcase24-slides/clinical-factflow-mentor-v8.pptx'),pythonExecutable:process.env.RUNTIME_PYTHON ?? '/Users/b787pw/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','4'],requiredNativeTableOwnerSlides:[4],requiredNativeChartOwnerSlides:[8,13,14],materializeLiteralChartWorkbooks:true,fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(root,'findings/medcase24-validation/validation-v8.json')});
console.log(JSON.stringify(result));
