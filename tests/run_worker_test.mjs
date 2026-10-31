// Uji Worker webhook (worker/worker.js) dengan io tiruan + situs uji lokal.
// Jalankan: node tests/run_worker_test.mjs
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PORT = 18081;
const HOST = `127.0.0.1:${PORT}`;
const SITE = `http://${HOST}`;
const OWNER = 424242;

let lulus = 0, gagal = 0;
function cek(nama, ok, detail = "") {
  if (ok) { lulus++; console.log("  LULUS  " + nama); }
  else { gagal++; console.log("  GAGAL  " + nama + " :: " + String(detail).slice(0, 220)); }
}

const regs = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "wk-")), "regs.jsonl");
const srv = spawn("python3", [path.join(ROOT, "testserver", "app.py"), String(PORT)],
  { env: { ...process.env, TESTSERVER_REGS: regs }, stdio: "ignore" });

async function tungguServer() {
  for (let i = 0; i < 50; i++) {
    try { const r = await fetch(SITE + "/"); if (r.ok) return; } catch (e) {}
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error("testserver tidak bangun");
}

function buatIo() {
  const kv = new Map();
  const terkirim = [];
  const dispatches = [];
  const io = {
    ownerId: OWNER,
    kvGet: async (k) => (kv.has(k) ? kv.get(k) : null),
    kvPut: async (k, v) => { kv.set(k, v); },
    kvDel: async (k) => { kv.delete(k); },
    send: async (chatId, text) => { terkirim.push([chatId, text]); },
    fetchText: async (url) => {
      const r = await fetch(url, { redirect: "follow" });
      return { url: r.url, status: r.status, text: await r.text() };
    },
    dispatch: async (jobId) => { dispatches.push(jobId); },
  };
  return { io, kv, terkirim, dispatches };
}

const upd = (chatId, text, id) => ({ update_id: id, message: { chat: { id: chatId }, text } });

try {
  await tungguServer();
  const { handleUpdate } = await import(pathToFileURL(path.join(ROOT, "worker", "worker.js")).href);

  console.log("1) Pemilik saja + sapaan");
  {
    const { io, terkirim } = buatIo();
    await handleUpdate(io, upd(999, "/start", 1));
    cek("non-pemilik diabaikan", terkirim.length === 0, JSON.stringify(terkirim));
    await handleUpdate(io, upd(OWNER, "/start", 2));
    cek("pemilik disapa", terkirim.length === 1 && terkirim[0][1].includes("Bot daftar website siap"),
        JSON.stringify(terkirim));
  }

  console.log("2) Alur penuh dari nama domain");
  const W = buatIo();
  const semua = () => W.terkirim.map(x => x[1]).join("\n");
  await handleUpdate(W.io, upd(OWNER, "/daftar", 3));
  cek("prompt minta nama domain", semua().includes("NAMA DOMAIN"), semua().slice(0, 150));
  await handleUpdate(W.io, upd(OWNER, HOST, 4));
  cek("domain -> kategori A + minta email",
      semua().includes("Kategori: A") && semua().includes("EMAIL"), semua().slice(-400));
  await handleUpdate(W.io, upd(OWNER, "uji@contoh.id", 5));
  cek("email -> nama acak ditawarkan", /Nama: .+\nUsername: /.test(semua()), semua().slice(-300));
  await handleUpdate(W.io, upd(OWNER, "GANTI", 6));
  cek("GANTI -> acakan baru", semua().includes("Acakan baru"), semua().slice(-200));
  await handleUpdate(W.io, upd(OWNER, "OK", 7));
  cek("OK -> minta password", semua().includes("PASSWORD"), semua().slice(-200));
  await handleUpdate(W.io, upd(OWNER, "RahasiaUji#123", 8));
  cek("password -> dispatch eksekusi 1x", W.dispatches.length === 1, JSON.stringify(W.dispatches));
  const jobKey = [...W.kv.keys()].find(k => k.startsWith("job:"));
  const job = jobKey ? JSON.parse(W.kv.get(jobKey)) : null;
  cek("job tersimpan sesaat di KV berisi data daftar",
      !!job && job.data.email === "uji@contoh.id" && job.data.password === "RahasiaUji#123",
      jobKey || "job tidak ada");
  const convJson = W.kv.get("conv:" + OWNER) || "{}";
  cek("state percakapan TIDAK mengandung password",
      !convJson.includes("RahasiaUji"), convJson.slice(0, 200));
  cek("balasan 'memproses' terkirim", semua().includes("Memproses pendaftarannya"), semua().slice(-200));

  console.log("3) Kategori B & C lewat URL langsung");
  {
    const B = buatIo();
    await handleUpdate(B.io, upd(OWNER, "/daftar", 9));
    await handleUpdate(B.io, upd(OWNER, SITE + "/daftar-captcha", 10));
    const t = B.terkirim.map(x => x[1]).join("\n");
    cek("CAPTCHA -> kategori B, berhenti", t.includes("Kategori: B") && t.includes("belum dieksekusi"), t.slice(-300));
  }
  {
    const C = buatIo();
    await handleUpdate(C.io, upd(OWNER, "/daftar", 11));
    await handleUpdate(C.io, upd(OWNER, SITE + "/daftar-otp", 12));
    const t = C.terkirim.map(x => x[1]).join("\n");
    cek("OTP SMS -> kategori C, ditolak", t.includes("Tidak bisa diproses") && t.includes("otp"), t.slice(-300));
  }
} finally {
  srv.kill();
}
console.log(`\nHASIL: ${lulus} lulus, ${gagal} gagal`);
process.exit(gagal ? 1 : 0);
