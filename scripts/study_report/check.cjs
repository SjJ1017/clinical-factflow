const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8'),payload=html.match(/<script id="studyData" type="application\/json">([\s\S]*?)<\/script>/)[1],script=html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
class Element{constructor(id){this.id=id;this.value='';this._html='';this.textContent=''}set innerHTML(v){this._html=v;if(v.startsWith('<option'))this.value=v.match(/value="([^"]+)"/)?.[1]||''}get innerHTML(){return this._html}}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id)};
for(const m of html.matchAll(/<select id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)){const opts=[...m[2].matchAll(/<option([^>]*)>(.*?)<\/option>/g)];const o=opts.find(o=>o[1].includes('selected'))||opts[0];if(o)get(m[1]).value=o[1].match(/value="([^"]+)"/)?.[1]||o[2]}
get('studyData').textContent=payload;let context={console,document:{getElementById:get}};vm.createContext(context);vm.runInContext(script,context);
vm.runInContext(`
let changes=0;
for(const metric of ['exact','fuzzy_same','fuzzy_inclusive'])for(const vote of ['literal_system','semantic_system'])for(const round of ['1','2','3']){$('accuracyMetric').value=metric;$('vote').value=vote;$('accuracyRound').value=round;renderAccuracy();changes++}
for(const q of ['facts','new_vs_outputs','new_vs_initial']){$('factQuantity').value=q;renderFacts();changes++}
for(const mode of ['equivalence','entailment'])for(const scheme of ['inclusive','fractional']){$('diversityMode').value=mode;$('diversityScheme').value=scheme;renderDiversity();changes++}
for(const unit of ['equivalence','atoms'])for(const scheme of ['inclusive','fractional'])for(const match of ['equivalence','entailment']){
 $('unit').value=unit;$('scheme').value=scheme;$('match').value=match;
 for(const metric of ['output_own','output_prime','output_other','share_shift','peer_excess']){$('outputMetric').value=metric;renderLoyalty();changes++}
 for(const metric of ['uptake_prime','uptake_own','uptake_other']){$('uptakeMetric').value=metric;renderLoyalty();changes++}
 for(const field of ['all','clinical','laboratory','imaging'])for(const rd of ['1','2','3']){$('contrastField').value=field;$('contrastRound').value=rd;renderContrasts();changes++}
 for(const c of D.conditions)for(const rd of ['2','3']){$('graphCondition').value=c;$('transition').value=rd;renderGraphs();changes++}
 $('graphAll').value='yes';renderGraphs();changes++;
}
for(const c of D.conditions)for(const rd of ['1','2','3'])for(const level of ['agent','literal_system','semantic_system']){$('diagnosisCondition').value=c;$('diagnosisRound').value=rd;$('diagnosisLevel').value=level;renderDiagnoses();const rows=($('diagnosisTable').innerHTML.match(/<tr>/g)||[]).length;if(rows!==(level==='agent'?73:25))throw Error('Diagnosis filter row count');changes++}
for(const [a,b,values] of [['graphScheme','scheme',['inclusive','fractional']],['graphUnit','unit',['atoms','equivalence']],['graphMatch','match',['entailment','equivalence']]])for(const v of values){$(a).value=v;$(a).onchange();if($(b).value!==v)throw Error('Graph control not synchronized');changes++}
$('scheme').value='fractional';$('unit').value='equivalence';$('match').value='equivalence';$('graphCondition').value='split-specialist';$('transition').value='3';$('graphAll').value='no';renderLoyalty();
console.log(JSON.stringify({controlConfigurationsChecked:changes,accuracyGroups:D.accuracy.length,profileGroups:D.profiles.length,graphGroups:D.graphs.length,graphDirectionsPerSetting:9}));
`,context);
for(let [id,el] of elements){assert(!el.innerHTML.includes('NaN'),id+' NaN');assert(!el.innerHTML.includes('undefined'),id+' undefined')}
for(const [i,svg] of [...get('graphPanels').innerHTML.matchAll(/<svg[\s\S]*?<\/svg>/g)].entries())fs.writeFileSync('/tmp/medcase-graph-'+i+'.svg',svg[0]);
assert.equal([...get('graphPanels').innerHTML.matchAll(/class="heat-cell"/g)].length,18);
assert.equal([...get('graphPanels').innerHTML.matchAll(/marker-end=/g)].length,0);
fs.writeFileSync('/tmp/medcase-accuracy.svg',get('agentAccuracy').innerHTML.replace(/class="annotation"/g,'font-size="11" fill="#687b80"'));
vm.runInContext(`
for(const unit of ['equivalence','atoms'])for(const scheme of ['fractional','inclusive'])for(const match of ['equivalence','entailment']){
 $('unit').value=unit;$('scheme').value=scheme;$('match').value=match;renderStrips();renderMismatch();
 const expected=D.followup.points.filter(r=>followupSelected(r)&&r.uptake_prime!=null).length;
 const actual=($('primeStrips').innerHTML.match(/class="case-agent-dot"/g)||[]).length;
 if(actual!==expected)throw Error('Scatter NA/point count mismatch');
 if(($('primeStrips').innerHTML.match(/<svg/g)||[]).length!==3)throw Error('Three aligned round panels required');
 for(const grading of ['same','inclusive'])for(const scope of ['all','professional']){$('sourceGrade').value=grading;$('sourceScope').value=scope;renderAssociations();if($('associationTable').innerHTML.includes('undefined'))throw Error('Association data missing')}
}
$('unit').value='equivalence';$('scheme').value='fractional';$('match').value='equivalence';$('sourceGrade').value='inclusive';$('sourceScope').value='all';renderStrips();renderAssociations();renderMismatch();
`,context);
for(const [i,svg] of [...get('primeStrips').innerHTML.matchAll(/<svg[\s\S]*?<\/svg>/g)].entries())fs.writeFileSync('/tmp/medcase-strip-'+i+'.svg',svg[0]);
for(let [id,el] of elements){assert(!el.innerHTML.includes('NaN'),id+' NaN');assert(!el.innerHTML.includes('undefined'),id+' undefined')}
console.log('Follow-up controls passed: eight scatter variants, 32 correctness variants, explicit NA counts.');
vm.runInContext(`
let socialStates=0;
for(let c of ['all',...D.conditions])for(let grade of ['same','inclusive'])for(let scope of ['all','professional'])for(let unit of ['equivalence','atoms'])for(let match of ['equivalence','entailment'])for(let measure of Object.keys(socialMeasureNames)){
 $('socialCondition').value=c;$('socialGrade').value=grade;$('socialScope').value=scope;$('socialUnit').value=unit;$('socialMatch').value=match;$('socialMeasure').value=measure;renderSocial();socialStates++;
 for(let id of ['socialAssociation','socialMajority','socialConflict','socialCoverage','socialFinding'])if(/NaN|undefined/.test($(id).innerHTML))throw Error(id+' contains invalid result');
 if(($('socialAssociation').innerHTML.match(/<tr>/g)||[]).length!==7)throw Error('Outcome strata table coverage');
}
console.log('Social uptake controls passed: '+socialStates+' combinations.');
`,context);
