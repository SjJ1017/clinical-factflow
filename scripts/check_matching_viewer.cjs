const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8'),payload=html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)[1],script=html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
class Element{constructor(id){this.id=id;this.value='';this.style={};this.checked=false;this._html='';this.textContent='';this.classList={remove(){},toggle(){}}}set innerHTML(v){this._html=v;if(this.id.endsWith('Select')||this.id==='threshold'){const m=v.match(/<option value="([^"]+)"/);this.value=m?.[1]||''}}get innerHTML(){return this._html}addEventListener(){}querySelectorAll(){return[]}getClientRects(){return[]}setAttribute(){}}
let el=new Map();const get=id=>{if(!el.has(id))el.set(id,new Element(id));return el.get(id)};get('payload').textContent=payload;get('infoSelect').value='shared';get('scope').value='output';
const ctx={console,document:{getElementById:get,querySelectorAll:()=>[],addEventListener(){},body:{style:{}}},location:{hash:''},history:{replaceState(){}},ResizeObserver:class{observe(){}},requestAnimationFrame(){},window:{addEventListener(){}}};vm.createContext(ctx);vm.runInContext(script,ctx);
vm.runInContext(`
let checked=0,links=0;
for(const r of DATA.runs){
 $('caseSelect').value=r.case;$('infoSelect').value=r.condition.split('-')[0];roleOptions(r.condition.split('-')[1]);render();
 if(run.id!==r.id)throw Error('Wrong selected run');
 if(($('rounds').innerHTML.match(/class="card jump output-card"/g)||[]).length!==9)throw Error('Wrong output count');
 for(const t of DATA.summary.thresholds){$('threshold').value=String(t);updateTraceMetrics();renderStudy()}
 $('threshold').value='5.28';choose(Number(Object.keys(run.atoms)[0]));if(!$('inspector').innerHTML.includes('Occurrences & labels'))throw Error('Inspector did not render');$('showSources').checked=true;$('showSelf').checked=true;
 for(const id of Object.keys(run.atoms)){
  selected=Number(id);highlight=new Set([selected]);for(const [other,s] of adj.get(selected)||[])if(pairType(s,5.28)===3)highlight.add(other);
  for(const e of getEdges()){
   const a=cards.get(e.from),b=cards.get(e.to);
   if(!b.visible.includes(a.id))throw Error('Invisible edge');
   if(a.channel==='output'&&a.round>=b.round)throw Error('Parallel/future edge');
   for(const [i,j] of e.pairs)if(!equivalent(i,j))throw Error('Non-equivalent wire');
   links++;
  }
  checked++;
 }
 for(const c of run.cards){
  const tagged=marked(c);const raw=tagged.replace(/<[^>]*>/g,'').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
  if(raw!==c.text)throw Error('Original text modified '+r.id+'/'+c.id);
 }
}
console.log(JSON.stringify({traces:DATA.runs.length,selectedAtomsChecked:checked,eligibleConnectionsChecked:links,thresholds:DATA.summary.thresholds.length,originalText:'exactly preserved'}));
// Test non-transitive equivalence and boundary behavior separately from saved corpus.
pairMap=new Map([['1,2',[1,2,6,6]],['2,3',[2,3,6,6]]]);
if(equivalent(1,3))throw Error('Transitive equivalence manufactured');
if(pairType([1,2,5.28,5.28],5.28)!==3||pairType([1,2,5.28,5.279],5.28)!==1)throw Error('Wrong >= boundary');
`,ctx);
