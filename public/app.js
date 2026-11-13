'use strict';
const $ = id => document.getElementById(id);
let state = {channels: [], active: ''};
let version = 0;
let batchId = '';
let selected = null;
let saving = false;
const uid = () => crypto.randomUUID();
const current = () => state.channels.find(c => c.id === state.active);
const batch = () => current()?.batches.find(b => b.id === batchId);
const say = text => { $('message').textContent = text; };
function element(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function action(text, fn) {
  const node = element('button', text, 'secondary');
  node.onclick = () => run(fn);
  return node;
}
async function run(fn) {
  try { await fn(); } catch (error) { say(error.message || '処理できませんでした。'); }
}
async function persist(next) {
  if (saving) throw new Error('保存中です。少し待ってから操作してください。');
  saving = true;
  $('saveStatus').textContent = 'この端末に保存中…';
  try {
    const response = await fetch('/api/state', {method:'POST',headers:{'Content-Type':'application/json','X-Thumbnail-Lab':'1'},body:JSON.stringify({version,data:next})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    state = next; version = result.version;
    $('saveStatus').textContent = 'この端末に保存済み';
  } catch(error) {
    $('saveStatus').textContent = '保存できませんでした';
    throw error;
  } finally { saving = false; }
}
async function updateChannel(nextChannel) {
  await persist({...state,channels:state.channels.map(c => c.id === nextChannel.id ? nextChannel : c)});
}
function requireChannel() {
  if (!current()) throw new Error('まずチャンネル名を登録してください。仮の名前でも始められます。');
  return current();
}
function download(name, content, type='text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const a = element('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function readImage(file) {
  if (!file || !['image/png','image/jpeg','image/webp'].includes(file.type)) throw new Error('PNG・JPEG・WebPの画像を選んでください。');
  if (file.size > 4*1024*1024) throw new Error('画像は1枚4MB以内にしてください。');
  const data = await new Promise((resolve,reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('画像を読み込めませんでした。')); reader.readAsDataURL(file);
  });
  await new Promise((resolve,reject) => { const image = new Image(); image.onload=resolve; image.onerror=()=>reject(new Error('画像の形式を確認してください。')); image.src=data; });
  return {id:uid(),name:file.name,data};
}
function imageNode(ref) {
  const img = element('img'); img.src = ref.data; img.alt = ref.name; return img;
}
function imageLink(ref) {
  const a = element('a','画像を保存'); a.href=ref.data; a.download=ref.name; return a;
}
function renderRefs() {
  const channel = current(); $('refs').replaceChildren();
  $('refCount').textContent = `${channel?.refs.length || 0}枚`;
  if (!channel?.refs.length) $('refs').append(element('p','まだお手本がありません。過去のサムネを追加してください。','empty'));
  for (const ref of channel?.refs || []) {
    const card=element('article',undefined,'refCard'); card.append(imageNode(ref));
    const body=element('div',undefined,'cardBody'); body.append(element('p',ref.name));
    body.append(action(ref.favorite ? '★ 今回のお手本' : '☆ お手本にする',async()=>{
      const c=requireChannel();
      if (!ref.favorite && c.refs.filter(r=>r.favorite).length>=5) throw new Error('今回のお手本は5枚までです。別のお手本の★を外してください。');
      await updateChannel({...c,refs:c.refs.map(r=>r.id===ref.id?{...r,favorite:!r.favorite}:r)}); renderRefs();
    }),imageLink(ref));
    if(ref.sourceUrl && /^https:\/\/(www\.)?youtube\.com\//.test(ref.sourceUrl)) {
      const sourceLink=element('a','参考にしたYouTube動画'); sourceLink.href=ref.sourceUrl;
      sourceLink.target='_blank'; sourceLink.rel='noopener noreferrer'; body.append(sourceLink);
    }
    card.append(body); $('refs').append(card);
  }
}
const variations = [
  'お手本に最も忠実な構図。文字と人物の比率を優先。',
  '同じ配色・字体を保ち、主役の大きさを少し強調。',
  '同じ作風を保ち、文字の配置と余白に変化をつける。',
  '同じ作風を保ち、主役の表情または視線で興味を引く。',
  '同じ作風を保ち、題材の見せ場をより明確にする。'
];
function buildPrompt(channel, brief) {
  const references=channel.refs.filter(r=>r.favorite);
  const history=channel.batches.filter(b=>b.adopted!==null && b.remember && b.reason.trim());
  return [
    'ChatGPTの画像生成で、サムネイルを5案、各案を独立した画像として作ってください。5枚を1枚に並べた比較画像にはしないでください。',
    `チャンネル：${channel.name}`, `今回の題材：${brief.topic}`, `画像に入れる正確な文字：${brief.headline || '文字なし'}`, `今回の要望：${brief.notes || 'なし'}`,
    '添付のお手本を実際に見て、字体・文字の太さ・縁取り・配色・人物の比率・余白・装飾を把握し、共通する作風を引き継いでください。画像が添付されていない場合は生成前に確認してください。',
    `添付するお手本：${references.map(r=>r.name).join('、')}`,
    `必ず守るルール：\n${channel.rules || 'お手本の作風に従う。'}`,
    '過去の採用理由（今回の明示指示を優先し、題材固有の内容は勝手に転用しない）：',
    ...(history.length?history.slice(-20).map(b=>`・${b.topic}／案${b.adopted+1}：${b.reason}`):['まだ履歴はありません。']),
    '不採用の理由が記録されていない案を、嫌いな作風と推測しないでください。',
    ...variations.map((v,i)=>`案${i+1}：${v}`),
    'お手本や明示ルールに反する変化は避ける。人物の同一性を保つ。文字の誤字、見切れ、不要な文字を確認する。比率はお手本に合わせる。'
  ].join('\n\n');
}
function renderCandidates() {
  const b=batch(); $('candidates').replaceChildren(); $('adopt').disabled=!b;
  $('reason').value=b?.reason || ''; $('remember').checked=b?.remember ?? true;
  $('briefOutput').hidden=!b;
  if (b) $('promptText').value=b.prompt;
  for (let i=0;i<5;i++) {
    const ref=b?.images[i]; const card=element('article',undefined,`candidate${selected===i?' selected':''}`);
    card.append(ref?imageNode(ref):element('div',`案 ${i+1} · 画像を登録`,'emptyImage'));
    const body=element('div',undefined,'cardBody'); body.append(element('b',`案 ${i+1}${b?.adopted===i?' · 採用済み':''}`));
    const input=element('input'); input.type='file'; input.accept='image/png,image/jpeg,image/webp'; input.disabled=!b;
    input.setAttribute('aria-label',`案${i+1}の画像を登録`);
    input.onchange=()=>run(async()=>{
      if (!input.files.length) return;
      const image=await readImage(input.files[0]); const c=requireChannel(); const currentBatch=batch();
      await updateChannel({...c,batches:c.batches.map(x=>x.id===currentBatch.id?{...x,images:x.images.map((old,j)=>j===i?image:old),adopted:x.adopted===i?null:x.adopted}:x)});
      renderCandidates();
    });
    body.append(input);
    const button=action(selected===i?'✓ 選択中':'この案を選ぶ',()=>{selected=i; renderSelection();});
    button.disabled=!ref; button.dataset.select=String(i); body.append(button);
    if(ref) body.append(imageLink(ref)); card.append(body); $('candidates').append(card);
  }
}
function renderSelection() {
  document.querySelectorAll('.candidate').forEach((card,i)=>card.classList.toggle('selected',selected===i));
  document.querySelectorAll('[data-select]').forEach(btn=>{btn.textContent=Number(btn.dataset.select)===selected?'✓ 選択中':'この案を選ぶ';});
}
function renderMemories() {
  const c=current(); const memories=(c?.batches || []).filter(b=>b.adopted!==null);
  $('memoryCount').textContent=`${memories.filter(b=>b.remember&&b.reason.trim()).length}件を反映`;
  $('memories').replaceChildren();
  if (!memories.length) $('memories').append(element('p','採用した案と理由が、ここに残ります。','empty'));
  for (const b of [...memories].reverse()) {
    const box=element('article',undefined,'memory');box.append(element('b',`${b.topic} · 案${b.adopted+1}`));
    box.append(element('p',b.reason || '理由は未記入です。選択結果だけを保存しています。'));
    box.append(element('small',new Date(b.created).toLocaleDateString('ja-JP')));
    box.append(action(b.remember?'次回への反映を止める':'次回へ反映する',async()=>{
      const latest=requireChannel(); await updateChannel({...latest,batches:latest.batches.map(x=>x.id===b.id?{...x,remember:!x.remember}:x)}); renderMemories();
      if(batchId===b.id)$('remember').checked=batch().remember;
    })); $('memories').append(box);
  }
}
function render() {
  const c=current(); $('channel').replaceChildren();
  if(!state.channels.length) $('channel').append(new Option('チャンネル未登録',''));
  state.channels.forEach(c=>$('channel').append(new Option(c.name,c.id))); $('channel').value=state.active;
  $('rules').value=c?.rules||''; renderRefs(); $('batch').replaceChildren();
  if(!c?.batches.length) $('batch').append(new Option('まず依頼文を作成してください',''));
  for(const b of [...(c?.batches||[])].reverse()) $('batch').append(new Option(b.topic,b.id));
  if(!c?.batches.some(b=>b.id===batchId)) batchId=c?.batches.at(-1)?.id||'';
  $('batch').value=batchId; selected=batch()?.adopted??null; renderCandidates();renderMemories();
}
$('addChannel').onclick=()=>{ $('channelForm').hidden=false; $('newChannelName').focus(); };
$('cancelChannel').onclick=()=>{ $('channelForm').hidden=true; };
$('confirmChannel').onclick=()=>run(async()=>{
  const name=$('newChannelName').value; if(!name.trim())throw new Error('チャンネル名を入力してください。');
  if(name.trim().length>80)throw new Error('チャンネル名は80文字以内にしてください。');
  const c={id:uid(),name:name.trim(),refs:[],rules:'',batches:[]};
  await persist({...state,active:c.id,channels:[...state.channels,c]});batchId='';render();$('channelForm').hidden=true;$('newChannelName').value='';
});
$('channel').onchange=()=>run(async()=>{await persist({...state,active:$('channel').value});batchId='';render();});
$('refsInput').onchange=()=>run(async()=>{
  const c=requireChannel(); const files=[...$('refsInput').files];
  if(c.refs.length+files.length>30)throw new Error('1チャンネルのお手本ライブラリは30枚までです。');
  const refs=await Promise.all(files.map(readImage)); const available=5-c.refs.filter(r=>r.favorite).length;
  await updateChannel({...c,refs:[...c.refs,...refs.map((r,i)=>({...r,favorite:i<available}))]});$('refsInput').value='';renderRefs();
});
$('saveRules').onclick=()=>run(async()=>{const c=requireChannel();await updateChannel({...c,rules:$('rules').value});say('作風ルールを保存しました。次の依頼文から反映します。');});
$('createBrief').onclick=()=>run(async()=>{
  const c=requireChannel(); const topic=$('topic').value.trim();
  if(!topic)throw new Error('今回の題材を入力してください。');
  if(!c.refs.some(r=>r.favorite))throw new Error('過去のサムネを追加し、今回のお手本に★を付けてください。');
  const brief={id:uid(),topic,headline:$('headline').value.trim(),notes:$('notes').value.trim(),created:new Date().toISOString(),images:Array(5).fill(null),adopted:null,reason:'',remember:true};
  const nextChannel={...c,rules:$('rules').value};
  const nextBrief={...brief,prompt:buildPrompt(nextChannel,brief),referenceIds:c.refs.filter(r=>r.favorite).map(r=>r.id)};
  await updateChannel({...nextChannel,batches:[...c.batches,nextBrief]});batchId=brief.id;render();
  say('依頼文を作りました。お手本画像と一緒に、このチャットに渡してください。');
});
$('batch').onchange=()=>{batchId=$('batch').value;selected=batch()?.adopted??null;renderCandidates();};
$('copyPrompt').onclick=()=>run(async()=>{await navigator.clipboard.writeText($('promptText').value);say('依頼文をコピーしました。お手本の画像もチャットへ添付してください。');});
$('downloadPrompt').onclick=()=>download('サムネ5案の依頼文.txt',$('promptText').value);
$('adopt').onclick=()=>run(async()=>{
  const c=requireChannel();const b=batch();if(!b||selected===null||!b.images[selected])throw new Error('画像のある案を選んでください。');
  await updateChannel({...c,batches:c.batches.map(x=>x.id===b.id?{...x,adopted:selected,reason:$('reason').value.trim(),remember:$('remember').checked}:x)});
  renderCandidates();renderMemories();say('採用案を保存しました。反映を有効にした理由は、次の依頼文に入ります。');
});
$('backup').onclick=()=>download('thumbnail-lab-backup.json',JSON.stringify(state,null,2),'application/json');
run(async()=>{const response=await fetch('/api/state');if(!response.ok)throw new Error('この端末に接続できません。');const result=await response.json();state=result.data;version=result.version;$('saveStatus').textContent='この端末に接続済み';render();});
