const a = /* @__PURE__ */ new Map();
function f(r, e = {}) {
  const c = new URL(r, window.location.href).href, i = e.id || c;
  if (a.has(i))
    return a.get(i);
  if (e.id ? document.getElementById(e.id) : Array.from(document.scripts).find((d) => new URL(d.src, window.location.href).href === c))
    return Promise.resolve();
  const l = new Promise((d, v) => {
    var o;
    const t = document.createElement("script");
    t.src = c, e.id && (t.id = e.id), e.type !== void 0 && e.type !== null && (t.type = e.type), t.async = e.async ?? !0, e.defer !== void 0 && (t.defer = e.defer);
    for (const [s, n] of Object.entries(e.attributes ?? {}))
      if (!(n == null || n === !1)) {
        if (n === !0) {
          t.setAttribute(s, "");
          continue;
        }
        t.setAttribute(s, n);
      }
    for (const [s, n] of Object.entries(e.dataset ?? {}))
      n != null && (t.dataset[s] = n);
    const u = (o = document.querySelector("script[nonce]")) == null ? void 0 : o.nonce;
    u && (t.nonce = u), t.addEventListener(
      "load",
      () => {
        a.delete(i), d();
      },
      { once: !0 }
    ), t.addEventListener(
      "error",
      () => {
        a.delete(i), t.remove(), v(new Error(`Failed to load script: ${c}`));
      },
      { once: !0 }
    ), (document.head || document.documentElement).appendChild(t);
  });
  return a.set(i, l), l;
}
const w = { type: "module" };
async function m(r) {
  const e = r != null && r.dev ? "https://stage.verstka.org/viewer-latest.js" : "https://verstka.org/viewer-latest.js", c = "http://localhost:5178/index.js";
  r != null && r.debug ? await f(c, w) : await f(e, w);
  const i = window;
  if (!i.Verstka)
    throw new Error("Verstka is not loaded");
  return i.Verstka;
}
async function h(r, e) {
  return (await m(e)).initArticle(r);
}
async function k(r, e) {
  return (await m(e)).initArticles(r);
}
export {
  h as initArticle,
  k as initArticles
};
