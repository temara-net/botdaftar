// Bot Daftar Website — versi WEBHOOK (selalu-nyala, balasan instan).
// Berjalan di Cloudflare Workers. Telegram memanggil endpoint ini tiap ada
// pesan; TIDAK ada jadwal dan TIDAK ada polling.
//
// Pembagian kerja:
// - Worker ini: percakapan Telegram + penemuan halaman daftar + pracek.
//   State percakapan disimpan di KV (binding BOTKV), TANPA password.
// - Saat pengguna mengirim password, Worker membuat "job" sesaat di KV
//   (job:<id>, TTL 15 menit, berisi data daftar + password) lalu memicu
//   workflow GitHub Actions execute.yml dengan job_id saja. Eksekutor di
//   Actions mengambil job itu, MENGHAPUSNYA, menjalankan pendaftaran via
//   browser, dan mengirim hasil + screenshot langsung ke Telegram.
//   Password tidak pernah masuk Git, state percakapan, log, atau input
//   workflow (input workflow terlihat di UI Actions — makanya hanya id).
//
// Env/secrets Worker: TG_BOT_TOKEN, OWNER_ID, WEBHOOK_SECRET, GH_TOKEN
// (token GitHub khusus dispatch workflow repo botdaftar), BOTKV (KV binding).

const GH_REPO = "temara-net/botdaftar";
const GH_WORKFLOW = "execute.yml";

const SAPA = "Halo pemilik. Bot daftar website siap.\n\n" +
  "Kirim /daftar untuk mulai mendaftar ke sebuah website.\n" +
  "Kirim /batal kapan saja untuk membatalkan proses yang berjalan.";

const DEPAN = ["Andini", "Bagas", "Citra", "Dimas", "Eka", "Fajar", "Gita", "Hadi",
  "Intan", "Joko", "Kartika", "Lukman", "Maya", "Nanda", "Oscar",
  "Putri", "Rian", "Sari", "Teguh", "Utami", "Vina", "Wahyu",
  "Yusuf", "Zahra", "Rama", "Sinta", "Bima", "Laras", "Galih", "Nadia"];
const BELAKANG = ["Pratama", "Saputra", "Wulandari", "Nugroho", "Anggraini",
  "Firmansyah", "Maharani", "Setiawan", "Handayani", "Prabowo",
  "Lestari", "Ramadhan", "Fitriani", "Gunawan", "Puspita",
  "Hakim", "Nugraha", "Salim", "Maulana", "Pertiwi"];

const CAPTCHA = ["recaptcha", "hcaptcha", "turnstile", "g-recaptcha", "cf-challenge", "captcha"];
const C_KUAT = ["kode otp", "otp sms", "verifikasi sms", "nomor ktp", "e-ktp",
  "kartu kredit", "credit card", "cvv", "biaya pendaftaran", "payment required"];
const B_KATA = ["verifikasi email", "email verification", "cek email anda", "check your email"];
const JALUR_UMUM = ["/register", "/signup", "/sign-up", "/daftar", "/registrasi",
  "/join", "/create-account", "/auth/register", "/user/register",
  "/account/register", "/pendaftaran", "/members/register"];
const KATA_LINK = ["daftar", "register", "signup", "sign-up", "sign up", "registrasi",
  "join", "gabung", "buat akun", "create account", "buka akun", "registration"];

const RE_URL = /^https?:\/\/\S+$/i;
const RE_EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// ---------------- util ----------------
function acak(arr) {
  const b = new Uint32Array(1);
  crypto.getRandomValues(b);
  return arr[b[0] % arr.length];
}

export function buatNama() {
  const nama = `${acak(DEPAN)} ${acak(BELAKANG)}`;
  const pisah = acak(["", ".", "_"]);
  let user = nama.toLowerCase().replace(/ /g, pisah).replace(/[^a-z0-9._]/g, "");
  user = user.slice(0, 18) + String(10 + Math.floor(Math.random() * 990));
  return [nama, user, "lokal"];
}

export function normalisasiDomain(teks) {
  let t = (teks || "").trim().toLowerCase();
  let skema = null;
  if (t.startsWith("http://")) { skema = "http"; t = t.slice(7); }
  else if (t.startsWith("https://")) { skema = "https"; t = t.slice(8); }
  const host = t.split("/")[0].split("?")[0].split("#")[0];
  if (!host || host.includes(" ") || host.includes("..")) return null;
  if (!/^[a-z0-9.-]+(:\d{1,5})?$/.test(host)) return null;
  if (!host.includes(".") && !host.startsWith("localhost")) return null;
  return [skema, host];
}

function teksStrip(html) {
  return html.replace(/<script[\s\S]*?<\/script>/gi, " ")
             .replace(/<style[\s\S]*?<\/style>/gi, " ")
             .replace(/<[^>]+>/g, " ")
             .replace(/\s+/g, " ").trim();
}

function ambilAttr(tag, nama) {
  const m = tag.match(new RegExp(nama + '\\s*=\\s*"([^"]*)"', "i")) ||
            tag.match(new RegExp(nama + "\\s*=\\s*'([^']*)'", "i")) ||
            tag.match(new RegExp(nama + "\\s*=\\s*([^\\s>]+)", "i"));
  return m ? m[1] : "";
}

// ---------------- pracek (port dari daftar/precheck.py) ----------------
export function pracekHtml(html, urlFinal) {
  const rendah = html.toLowerCase();
  const formRe = /<form\b[^>]*>[\s\S]*?<\/form>/gi;
  const forms = html.match(formRe) || [];
  const kandidat = [];
  for (const f of forms) {
    if (/type\s*=\s*["']?password/i.test(f)) kandidat.push(f);
  }
  if (!kandidat.length) {
    return { kategori: "C", alasan: "Tidak ditemukan formulir daftar (halaman ini tidak punya " +
      "kolom password). Mungkin pendaftaran ada di halaman lain, " +
      "atau situs hanya menerima pendaftaran lewat aplikasi/undangan." };
  }
  function skorForm(f) {
    let skor = 5;
    const kepala = (f.match(/<form\b[^>]*>/i) || [""])[0].toLowerCase();
    for (const k of ["daftar", "register", "signup", "sign-up", "registrasi", "join"]) {
      if (kepala.includes(k)) skor += 3;
    }
    skor += (f.match(/<input\b/gi) || []).length;
    return skor;
  }
  kandidat.sort((a, b) => skorForm(b) - skorForm(a));
  const form = kandidat[0];
  const kepala = (form.match(/<form\b[^>]*>/i) || [""])[0];

  const teksHalaman = teksStrip(html).toLowerCase();
  for (const kata of C_KUAT) {
    if (teksHalaman.includes(kata)) {
      return { kategori: "C", alasan: `Situs terdeteksi membutuhkan '${kata}' — di luar batas ` +
        "bot sesuai konsep (kategori C)." };
    }
  }

  const kolom = [];
  const tagRe = /<(input|select|textarea)\b[^>]*>/gi;
  let m;
  while ((m = tagRe.exec(form)) !== null) {
    const tag = m[0];
    const tipe = (ambilAttr(tag, "type") || m[1]).toLowerCase();
    if (["submit", "button", "image", "reset"].includes(tipe)) continue;
    const teks = [ambilAttr(tag, "name"), ambilAttr(tag, "id"),
                  ambilAttr(tag, "placeholder"), ambilAttr(tag, "aria-label"), tipe]
                 .filter(Boolean).join(" ").toLowerCase();
    kolom.push({ name: ambilAttr(tag, "name"), type: tipe,
                 required: /\brequired\b/i.test(tag), teks });
  }

  const adaCaptcha = CAPTCHA.some(c => rendah.includes(c));
  const actionMentah = ambilAttr(kepala, "action");
  const hasil = {
    url_form: urlFinal,
    action: new URL(actionMentah || urlFinal, urlFinal).toString(),
    method: (ambilAttr(kepala, "method") || "get").toLowerCase(),
    kolom,
    verifikasi_email: B_KATA.some(k => teksHalaman.includes(k)),
  };
  if (adaCaptcha) {
    hasil.kategori = "B";
    hasil.alasan = "Formulir memakai CAPTCHA — kategori B (semi-otomatis) " +
                   "belum dieksekusi di tahap MVP ini.";
  } else {
    hasil.kategori = "A";
    hasil.alasan = "Formulir biasa tanpa CAPTCHA.";
  }
  return hasil;
}

async function pracekUrl(io, url) {
  let r;
  try {
    r = await io.fetchText(url);
  } catch (e) {
    return { kategori: "C", alasan: `Situs tidak bisa dibuka: ${e.message || e}` };
  }
  if (r.status >= 400) {
    return { kategori: "C", alasan: `Situs tidak bisa dibuka: HTTP ${r.status}` };
  }
  return pracekHtml(r.text, r.url);
}

// ---------------- penemuan halaman daftar dari nama domain ----------------
export async function temukan(io, teks) {
  const norm = normalisasiDomain(teks);
  if (!norm) {
    return { kategori: "C", alasan: "Itu belum berbentuk nama domain. Contoh format: contoh.com" };
  }
  const [skema, host] = norm;
  const skemas = skema ? [skema] : ["https", "http"];
  let beranda = null;
  for (const sk of skemas) {
    try {
      const r = await io.fetchText(`${sk}://${host}/`);
      if (r.status < 500) { beranda = r; break; }
    } catch (e) { /* coba skema berikutnya */ }
  }
  if (!beranda) {
    return { kategori: "C", alasan: `Domain ${host} tidak bisa dibuka dari sini (koneksi gagal ` +
      "di https maupun http). Periksa lagi ejaan domainnya." };
  }
  const basis = beranda.url.endsWith("/") ? beranda.url : beranda.url.replace(/[^/]*$/, "");
  const kandidat = [];
  const linkRe = /<a\b[^>]*href\s*=\s*"([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
  let lm;
  const akar = host.split(":")[0].split(".").slice(-2).join(".");
  while ((lm = linkRe.exec(beranda.text)) !== null) {
    const gab = (lm[1] + " " + teksStrip(lm[2])).toLowerCase();
    if (!KATA_LINK.some(k => gab.includes(k))) continue;
    let u;
    try { u = new URL(lm[1], beranda.url).toString(); } catch (e) { continue; }
    const nu = normalisasiDomain(u);
    if (!nu) continue;
    const hostK = nu[1].split(":")[0];
    if ((hostK === host.split(":")[0] || hostK.endsWith("." + akar)) && !kandidat.includes(u)) {
      kandidat.push(u);
    }
  }
  // Peringkat AI: versi webhook memakai penelusuran deterministik;
  // (di bot Actions, AI memilih bila kunci AI terisi — lihat precheck.py).
  for (const jalur of JALUR_UMUM) {
    const u = new URL(jalur.slice(1), basis).toString();
    if (!kandidat.includes(u)) kandidat.push(u);
  }
  const daftar = kandidat.slice(0, 8);
  let terbaikB = null;
  for (const u of daftar) {
    const info = await pracekUrl(io, u);
    if (info.kategori === "A") { info.sumber_pilih = "penelusuran"; return info; }
    if (info.kategori === "B" && !terbaikB) terbaikB = info;
  }
  if (terbaikB) { terbaikB.sumber_pilih = "penelusuran"; return terbaikB; }
  return { kategori: "C", sumber_pilih: "penelusuran",
    alasan: `Sudah ditelusuri di ${host} (beranda + ${daftar.length} kandidat ` +
      "tautan/jalur umum), tapi tidak ditemukan halaman pendaftaran " +
      "dengan formulir. Mungkin pendaftaran hanya lewat aplikasi, " +
      "undangan, atau subdomain lain." };
}

// ---------------- mesin percakapan ----------------
function ringkasForm(info) {
  const baris = [`Kategori: ${info.kategori} — ${info.alasan}`,
                 `Halaman: ${info.url_form}`, "Kolom formulir:"];
  for (const k of info.kolom || []) {
    baris.push(`- ${k.name || "(tanpa nama)"} [${k.type}]${k.required ? " (wajib)" : ""}`);
  }
  return baris.join("\n");
}

export async function handleUpdate(io, update) {
  const msg = update.message || {};
  const chatId = msg.chat && msg.chat.id;
  const text = (msg.text || "").trim();
  if (chatId == null) return;
  if (String(chatId) !== String(io.ownerId)) return; // khusus pemilik

  const kunci = "conv:" + chatId;
  let c = {};
  try { c = JSON.parse((await io.kvGet(kunci)) || "{}"); } catch (e) { c = {}; }
  const simpan = async () => io.kvPut(kunci, JSON.stringify(c));
  const reset = async () => { c = {}; await io.kvPut(kunci, "{}"); };
  const stage = c.stage || "idle";
  const t = text;
  const rendah = t.toLowerCase();

  if (rendah === "/start" || rendah === "/help") { await io.send(chatId, SAPA); return; }
  if (rendah === "/batal") {
    await reset();
    await io.send(chatId, "Proses dibatalkan. Kirim /daftar untuk mulai lagi.");
    return;
  }
  if (rendah === "/daftar") {
    c = { stage: "wait_url" };
    await simpan();
    await io.send(chatId, "Kirim NAMA DOMAIN website tujuannya saja " +
      "(contoh: contoh.com) — bot yang mencarikan halaman " +
      "daftarnya. Kalau sudah tahu alamat pastinya, URL " +
      "lengkap halaman daftar juga boleh.");
    return;
  }

  if (stage === "wait_url") {
    if (!normalisasiDomain(t)) {
      await io.send(chatId, "Itu belum berbentuk nama domain. Cukup ketik " +
        "domainnya saja, contoh: contoh.com — atau /batal.");
      return;
    }
    let path = "";
    if (t.includes("://")) {
      const sisa = t.split("://", 2)[1] || "";
      path = sisa.includes("/") ? sisa.split("/").slice(1).join("/") : "";
    }
    const langsung = RE_URL.test(t) && path.replace(/\//g, "") !== "";
    let info;
    if (langsung) {
      await io.send(chatId, "Memeriksa halaman itu dulu...");
      info = await pracekUrl(io, t);
    } else {
      await io.send(chatId, "Mencari halaman daftar di domain itu...");
      info = await temukan(io, t);
    }
    if (info.kategori === "C") {
      await reset();
      await io.send(chatId, `Tidak bisa diproses.\n\n${info.alasan}\n\n` +
        "Kirim /daftar untuk mencoba website lain.");
      return;
    }
    if (info.kategori === "B") {
      await reset();
      await io.send(chatId, ringkasForm(info) + "\n\nKategori B (ada CAPTCHA) " +
        "belum dieksekusi di tahap ini — sesuai konsep, itu " +
        "tahap berikutnya. Proses berhenti di sini.");
      return;
    }
    c = { stage: "wait_email", info };
    await simpan();
    let ketemu = "";
    if (info.sumber_pilih) {
      ketemu = "Halaman daftarnya ketemu — dicari oleh penelusuran bot.\n\n";
    }
    await io.send(chatId, ketemu + ringkasForm(info) + "\n\nSitusnya kategori A dan bisa " +
      "diproses. Sekarang kirim EMAIL " +
      "yang mau dipakai untuk akun ini " +
      "(email kamu sendiri — verifikasi " +
      "masuk ke sana).");
    return;
  }

  if (stage === "wait_email") {
    if (!RE_EMAIL.test(t)) {
      await io.send(chatId, "Format emailnya belum benar. Kirim ulang emailnya, atau /batal.");
      return;
    }
    const [nama, user, sumber] = buatNama();
    c = { ...c, stage: "wait_name", email: t, name: nama, username: user, ganti: 0 };
    await simpan();
    await io.send(chatId, `Nama + username acak (dari ${sumber}):\n\n` +
      `Nama: ${nama}\nUsername: ${user}\n\n` +
      "Balas OK untuk memakai ini, atau GANTI untuk acakan lain " +
      "(maks 3x).");
    return;
  }

  if (stage === "wait_name") {
    if (rendah === "ganti") {
      if ((c.ganti || 0) >= 3) {
        await io.send(chatId, "Batas ganti acakan (3x) habis. Balas OK untuk " +
          "memakai yang terakhir ini, atau /batal.");
        return;
      }
      const [nama, user, sumber] = buatNama();
      c = { ...c, name: nama, username: user, ganti: (c.ganti || 0) + 1 };
      await simpan();
      await io.send(chatId, `Acakan baru (dari ${sumber}):\n\nNama: ${nama}\n` +
        `Username: ${user}\n\nBalas OK atau GANTI.`);
      return;
    }
    if (rendah === "ok") {
      c = { ...c, stage: "wait_password" };
      await simpan();
      await io.send(chatId, "Terakhir: kirim PASSWORD untuk akun baru ini.\n\n" +
        "Pakai password khusus yang tidak dipakai di tempat " +
        "lain. Password hanya dipakai selama proses ini " +
        "berjalan — tidak disimpan bot dan tidak muncul di " +
        "laporan hasil. Sesudah proses selesai, hapus pesan " +
        "password ini dari chat.");
      return;
    }
    await io.send(chatId, "Balas OK untuk memakai nama itu, atau GANTI untuk acakan lain.");
    return;
  }

  if (stage === "wait_password") {
    const password = t;
    const jobId = crypto.randomUUID();
    const job = {
      chat_id: chatId,
      info: c.info || {},
      data: { name: c.name || "", username: c.username || "",
              email: c.email || "", password },
    };
    await io.kvPut("job:" + jobId, JSON.stringify(job), 900); // TTL 15 menit
    await reset();
    try {
      await io.dispatch(jobId);
      await io.send(chatId, "Memproses pendaftarannya sekarang... " +
        "Hasil + tangkapan layarnya dikirim ke sini begitu selesai (biasanya 1-3 menit).");
    } catch (e) {
      await io.kvDel("job:" + jobId);
      await io.send(chatId, "Gagal memulai proses pendaftaran " +
        `(pemicu eksekusi error: ${e.message || e}). Kirim /daftar untuk mencoba lagi.`);
    }
    return;
  }

  await io.send(chatId, "Kirim /daftar untuk mulai mendaftar ke website.");
}

// ---------------- adaptor Cloudflare ----------------
function buatIo(env) {
  const base = `https://api.telegram.org/bot${env.TG_BOT_TOKEN}/`;
  return {
    ownerId: env.OWNER_ID,
    kvGet: (k) => env.BOTKV.get(k),
    kvPut: (k, v, ttl) => env.BOTKV.put(k, v, ttl ? { expirationTtl: ttl } : undefined),
    kvDel: (k) => env.BOTKV.delete(k),
    send: async (chatId, text) => {
      for (let i = 0; i < text.length; i += 4000) {
        const r = await fetch(base + "sendMessage", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: chatId, text: text.slice(i, i + 4000) }),
        });
        if (!r.ok) throw new Error("Telegram sendMessage HTTP " + r.status);
      }
    },
    fetchText: async (url) => {
      const r = await fetch(url, {
        headers: { "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
                   "(KHTML, like Gecko) Chrome/124 Safari/537.36" },
        redirect: "follow",
      });
      return { url: r.url, status: r.status, text: await r.text() };
    },
    dispatch: async (jobId) => {
      const r = await fetch(
        `https://api.github.com/repos/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/dispatches`, {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + env.GH_TOKEN,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "botdaftar-worker",
          },
          body: JSON.stringify({ ref: "main", inputs: { job_id: jobId } }),
        });
      if (r.status !== 204) throw new Error("GitHub dispatch HTTP " + r.status);
    },
  };
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("botdaftar webhook aktif", { status: 200 });
    }
    if (env.WEBHOOK_SECRET) {
      const h = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
      if (h !== env.WEBHOOK_SECRET) return new Response("forbidden", { status: 403 });
    }
    let update;
    try { update = await request.json(); } catch (e) {
      return new Response("bad json", { status: 400 });
    }
    const io = buatIo(env);
    ctx.waitUntil(handleUpdate(io, update).catch(e =>
      console.log("handleUpdate error:", e && e.message)));
    return new Response("ok", { status: 200 });
  },
};
