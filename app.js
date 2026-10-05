const $ = (id) => document.getElementById(id);
const urlInput = $("url"), goBtn = $("go"), msg = $("msg"), results = $("results");

function say(text, isError = false) {
  msg.textContent = text;
  msg.className = isError ? "error" : "";
}

$("paste").addEventListener("click", async () => {
  try {
    urlInput.value = (await navigator.clipboard.readText()).trim();
    urlInput.focus();
  } catch {
    say("क्लिपबोर्ड नहीं खुला। लिंक को बॉक्स में दबाकर पेस्ट करें।", true);
  }
});

urlInput.addEventListener("keydown", (e) => { if (e.key === "Enter") goBtn.click(); });

goBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  results.innerHTML = "";
  if (!url) return say("पहले Instagram का लिंक डालें।", true);
  goBtn.disabled = true;
  say("खोज रहे हैं…");
  try {
    const r = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "कुछ गड़बड़ हो गई।");
    say(data.items.length > 1 ? `${data.items.length} आइटम मिले।` : "फ़ाइल तैयार है।");
    render(data);
  } catch (err) {
    say(err.message, true);
  } finally {
    goBtn.disabled = false;
  }
});

function fmt(sec) {
  if (!sec) return "";
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function render({ url, items }) {
  const q = encodeURIComponent(url);
  items.forEach((it) => {
    const card = document.createElement("article");
    card.className = "item";

    const img = document.createElement("img");
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    if (it.thumbnail) img.src = it.thumbnail;

    const body = document.createElement("div");
    const h = document.createElement("h2");
    h.textContent = it.title;
    const meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = [it.uploader, fmt(it.duration)].filter(Boolean).join(" • ");
    const actions = document.createElement("div");
    actions.className = "actions";

    const add = (label, href) => {
      const a = document.createElement("a");
      a.className = "dl";
      a.href = href;
      a.textContent = label;
      a.addEventListener("click", () => {
        a.classList.add("busy");
        setTimeout(() => a.classList.remove("busy"), 6000);
      });
      actions.appendChild(a);
    };

    if (it.video) add("वीडियो (MP4)", `/api/download?url=${q}&kind=video&item=${it.index}`);
    if (it.audio) add("ऑडियो (MP3)", `/api/download?url=${q}&kind=audio&item=${it.index}`);
    if (it.image) add("फोटो", `/api/image?src=${encodeURIComponent(it.thumbnail)}`);

    body.append(h, meta, actions);
    card.append(img, body);
    results.appendChild(card);
  });
}
