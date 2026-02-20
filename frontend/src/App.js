import { useState, useCallback, useRef, createContext, useContext } from "react";
import "@/App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DURATIONS = [3, 5, 7, 14, 30, 60, 100];

/* ─── i18n ─── */
const LANGS = {
  en: {
    flag: "EN",
    upload: "Upload", proxy: "Proxy",
    title: "GigaFile Upload", subtitle: "Upload files up to 300 GB",
    dropText: "Drop file here or click to select",
    orPasteUrl: "or paste URL",
    duration: "Duration",
    uploadBtn: "Upload",
    uploading: "Uploading... {p}%",
    uploadComplete: "Upload Complete",
    pageUrl: "Page URL",
    directUrl: "Direct URL",
    directHint: "(needs cookies)",
    proxyUrl: "Proxy URL",
    proxyHint: "(no cookies needed)",
    file: "File",
    expires: "Expires",
    uploadAnother: "Upload Another",
    copy: "Copy",
    copied: "Copied!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Download without cookies",
    download: "Download",
    tgBot: "Telegram Bot",
  },
  ru: {
    flag: "RU",
    upload: "Загрузка", proxy: "Прокси",
    title: "GigaFile Загрузка", subtitle: "Файлы до 300 ГБ",
    dropText: "Перетащи файл сюда или нажми для выбора",
    orPasteUrl: "или вставь URL",
    duration: "Срок хранения",
    uploadBtn: "Загрузить",
    uploading: "Загрузка... {p}%",
    uploadComplete: "Загрузка завершена",
    pageUrl: "Страница",
    directUrl: "Прямая ссылка",
    directHint: "(нужны куки)",
    proxyUrl: "Прокси-ссылка",
    proxyHint: "(без куки)",
    file: "Файл",
    expires: "Истекает",
    uploadAnother: "Загрузить ещё",
    copy: "Копировать",
    copied: "Скопировано!",
    proxyTitle: "GigaFile Прокси",
    proxySub: "Скачивание без куки",
    download: "Скачать",
    tgBot: "Telegram Бот",
  },
  es: {
    flag: "ES",
    upload: "Subir", proxy: "Proxy",
    title: "GigaFile Subir", subtitle: "Archivos hasta 300 GB",
    dropText: "Arrastra un archivo aqui o haz clic",
    orPasteUrl: "o pega una URL",
    duration: "Duracion",
    uploadBtn: "Subir",
    uploading: "Subiendo... {p}%",
    uploadComplete: "Subida completa",
    pageUrl: "Pagina",
    directUrl: "Enlace directo",
    directHint: "(necesita cookies)",
    proxyUrl: "Enlace proxy",
    proxyHint: "(sin cookies)",
    file: "Archivo",
    expires: "Expira",
    uploadAnother: "Subir otro",
    copy: "Copiar",
    copied: "Copiado!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Descarga sin cookies",
    download: "Descargar",
    tgBot: "Bot Telegram",
  },
  de: {
    flag: "DE",
    upload: "Hochladen", proxy: "Proxy",
    title: "GigaFile Upload", subtitle: "Dateien bis 300 GB",
    dropText: "Datei hierher ziehen oder klicken",
    orPasteUrl: "oder URL einfugen",
    duration: "Dauer",
    uploadBtn: "Hochladen",
    uploading: "Hochladen... {p}%",
    uploadComplete: "Upload abgeschlossen",
    pageUrl: "Seite",
    directUrl: "Direkter Link",
    directHint: "(Cookies erforderlich)",
    proxyUrl: "Proxy-Link",
    proxyHint: "(ohne Cookies)",
    file: "Datei",
    expires: "Ablauf",
    uploadAnother: "Weiteres hochladen",
    copy: "Kopieren",
    copied: "Kopiert!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Download ohne Cookies",
    download: "Herunterladen",
    tgBot: "Telegram Bot",
  },
  fr: {
    flag: "FR",
    upload: "Telecharger", proxy: "Proxy",
    title: "GigaFile Upload", subtitle: "Fichiers jusqu'a 300 Go",
    dropText: "Deposez un fichier ici ou cliquez",
    orPasteUrl: "ou collez une URL",
    duration: "Duree",
    uploadBtn: "Telecharger",
    uploading: "Telechargement... {p}%",
    uploadComplete: "Telechargement termine",
    pageUrl: "Page",
    directUrl: "Lien direct",
    directHint: "(cookies requis)",
    proxyUrl: "Lien proxy",
    proxyHint: "(sans cookies)",
    file: "Fichier",
    expires: "Expire",
    uploadAnother: "Telecharger un autre",
    copy: "Copier",
    copied: "Copie!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Telechargement sans cookies",
    download: "Telecharger",
    tgBot: "Bot Telegram",
  },
  ja: {
    flag: "JA",
    upload: "Upload", proxy: "Proxy",
    title: "GigaFile Upload", subtitle: "300 GB made file upload",
    dropText: "Drop file here or click",
    orPasteUrl: "or paste URL",
    duration: "Duration",
    uploadBtn: "Upload",
    uploading: "Uploading... {p}%",
    uploadComplete: "Upload Complete",
    pageUrl: "Page URL",
    directUrl: "Direct URL",
    directHint: "(cookies needed)",
    proxyUrl: "Proxy URL",
    proxyHint: "(no cookies)",
    file: "File",
    expires: "Expires",
    uploadAnother: "Upload Another",
    copy: "Copy",
    copied: "Copied!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Download without cookies",
    download: "Download",
    tgBot: "Telegram Bot",
  },
  zh: {
    flag: "ZH",
    upload: "Upload", proxy: "Proxy",
    title: "GigaFile Upload", subtitle: "Upload up to 300 GB",
    dropText: "Drop file here or click",
    orPasteUrl: "or paste URL",
    duration: "Duration",
    uploadBtn: "Upload",
    uploading: "Uploading... {p}%",
    uploadComplete: "Upload Complete",
    pageUrl: "Page URL",
    directUrl: "Direct URL",
    directHint: "(cookies needed)",
    proxyUrl: "Proxy URL",
    proxyHint: "(no cookies)",
    file: "File",
    expires: "Expires",
    uploadAnother: "Upload Another",
    copy: "Copy",
    copied: "Copied!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Download without cookies",
    download: "Download",
    tgBot: "Telegram Bot",
  },
  pt: {
    flag: "PT",
    upload: "Enviar", proxy: "Proxy",
    title: "GigaFile Upload", subtitle: "Arquivos ate 300 GB",
    dropText: "Arraste um arquivo ou clique",
    orPasteUrl: "ou cole uma URL",
    duration: "Duracao",
    uploadBtn: "Enviar",
    uploading: "Enviando... {p}%",
    uploadComplete: "Envio completo",
    pageUrl: "Pagina",
    directUrl: "Link direto",
    directHint: "(precisa cookies)",
    proxyUrl: "Link proxy",
    proxyHint: "(sem cookies)",
    file: "Arquivo",
    expires: "Expira",
    uploadAnother: "Enviar outro",
    copy: "Copiar",
    copied: "Copiado!",
    proxyTitle: "GigaFile Proxy",
    proxySub: "Download sem cookies",
    download: "Baixar",
    tgBot: "Bot Telegram",
  },
};

function detectLang() {
  const stored = localStorage.getItem("gf_lang");
  if (stored && LANGS[stored]) return stored;
  const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
  return LANGS[nav] ? nav : "en";
}

const LangContext = createContext({ lang: "en", t: LANGS.en, setLang: () => {} });

function useLang() {
  return useContext(LangContext);
}

/* ─── Language Picker ─── */
function LangPicker() {
  const { lang, setLang } = useLang();
  const [open, setOpen] = useState(false);
  return (
    <div className="lang-picker" data-testid="lang-picker">
      <button className="lang-btn" data-testid="lang-toggle" onClick={() => setOpen(!open)}>
        {LANGS[lang].flag}
      </button>
      {open && (
        <div className="lang-dropdown" data-testid="lang-dropdown">
          {Object.keys(LANGS).map((code) => (
            <button
              key={code}
              data-testid={`lang-${code}`}
              className={`lang-option ${code === lang ? "active" : ""}`}
              onClick={() => { setLang(code); setOpen(false); }}
            >
              {LANGS[code].flag}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Upload Page ─── */
function UploadPage() {
  const { t } = useLang();
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState("");
  const [duration, setDuration] = useState(100);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [copied, setCopied] = useState("");
  const fileInputRef = useRef(null);

  const reset = () => {
    setFile(null); setUrl(""); setResult(null); setError(null);
    setProgress(0); setCopied("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUpload = async () => {
    if (!file && !url.trim()) return;
    setUploading(true); setError(null); setResult(null); setProgress(0);
    try {
      const formData = new FormData();
      if (file) formData.append("file", file);
      else formData.append("url", url.trim());
      formData.append("duration", duration.toString());
      const resp = await axios.post(`${API}/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => { if (e.total) setProgress(Math.round((e.loaded * 100) / e.total)); },
      });
      if (resp.data.success) setResult(resp.data);
      else setError(resp.data.error || "Upload failed");
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Upload failed");
    } finally { setUploading(false); }
  };

  const handleDrag = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault(); e.stopPropagation(); setDragActive(false);
    if (e.dataTransfer.files?.[0]) { setFile(e.dataTransfer.files[0]); setUrl(""); }
  }, []);

  const copyTo = (text, label) => {
    navigator.clipboard.writeText(text).then(() => { setCopied(label); setTimeout(() => setCopied(""), 1500); }).catch(() => {});
  };

  const fmtSize = (b) => {
    if (!b) return "";
    if (b < 1024) return `${b} B`;
    if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
    if (b < 1073741824) return `${(b / 1048576).toFixed(1)} MB`;
    return `${(b / 1073741824).toFixed(2)} GB`;
  };

  return (
    <div className="page" data-testid="upload-page">
      <header className="header" data-testid="header">
        <h1>{t.title}</h1>
        <p className="sub">{t.subtitle}</p>
      </header>
      <main className="main">
        {!result ? (
          <div className="card" data-testid="upload-card">
            <div data-testid="drop-zone"
              className={`dropzone ${dragActive ? "active" : ""} ${file ? "has-file" : ""}`}
              onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
              onClick={() => !file && fileInputRef.current?.click()}>
              <input ref={fileInputRef} type="file" data-testid="file-input" className="hidden-input"
                onChange={(e) => { if (e.target.files?.[0]) { setFile(e.target.files[0]); setUrl(""); } }} />
              {file ? (
                <div className="file-info" data-testid="file-info">
                  <span className="file-icon">&#x1F4C4;</span>
                  <div><div className="file-name">{file.name}</div><div className="file-size">{fmtSize(file.size)}</div></div>
                  <button data-testid="remove-file-btn" className="remove-btn"
                    onClick={(e) => { e.stopPropagation(); setFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}>&times;</button>
                </div>
              ) : (
                <div className="drop-text"><span className="drop-icon">+</span><span>{t.dropText}</span></div>
              )}
            </div>
            {!file && (
              <div className="url-section" data-testid="url-section">
                <div className="divider"><span>{t.orPasteUrl}</span></div>
                <input data-testid="url-input" type="text" className="input" placeholder="https://example.com/file.zip"
                  value={url} onChange={(e) => setUrl(e.target.value)} />
              </div>
            )}
            <div className="settings" data-testid="settings">
              <div className="setting-group">
                <label>{t.duration}</label>
                <div className="duration-pills" data-testid="duration-pills">
                  {DURATIONS.map((d) => (
                    <button key={d} data-testid={`duration-${d}`} className={`pill ${duration === d ? "active" : ""}`}
                      onClick={() => setDuration(d)}>{d}d</button>
                  ))}
                </div>
              </div>
            </div>
            <button data-testid="upload-btn" className="upload-btn" disabled={uploading || (!file && !url.trim())} onClick={handleUpload}>
              {uploading ? t.uploading.replace("{p}", progress) : t.uploadBtn}
            </button>
            {uploading && <div className="progress-bar" data-testid="progress-bar"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>}
            {error && <div className="error" data-testid="error-msg">{error}</div>}
          </div>
        ) : (
          <div className="card result-card" data-testid="result-card">
            <h2>{t.uploadComplete}</h2>
            <div className="link-group" data-testid="page-url-group">
              <label>{t.pageUrl}</label>
              <div className="link-row">
                <code data-testid="page-url">{result.url}</code>
                <button data-testid="copy-page-url" className="copy-btn" onClick={() => copyTo(result.url, "page")}>
                  {copied === "page" ? t.copied : t.copy}</button>
              </div>
            </div>
            <div className="link-group" data-testid="raw-url-group">
              <label>{t.directUrl} <span className="optional">{t.directHint}</span></label>
              <div className="link-row">
                <code data-testid="raw-url">{result.raw_url}</code>
                <button data-testid="copy-raw-url" className="copy-btn" onClick={() => copyTo(result.raw_url, "raw")}>
                  {copied === "raw" ? t.copied : t.copy}</button>
              </div>
            </div>
            <div className="link-group" data-testid="proxy-url-group">
              <label>{t.proxyUrl} <span className="optional">{t.proxyHint}</span></label>
              <div className="link-row">
                <code data-testid="proxy-url">{result.proxy_url}</code>
                <button data-testid="copy-proxy-url" className="copy-btn" onClick={() => copyTo(result.proxy_url, "proxy")}>
                  {copied === "proxy" ? t.copied : t.copy}</button>
              </div>
            </div>
            {result.filename && <div className="meta" data-testid="filename-info">{t.file}: {result.filename}</div>}
            {result.expires && <div className="meta" data-testid="expires-info">{t.expires}: {new Date(result.expires).toLocaleDateString()}</div>}
            <button data-testid="upload-another-btn" className="upload-btn secondary" onClick={reset}>{t.uploadAnother}</button>
          </div>
        )}
        <div className="api-docs" data-testid="api-docs">
          <h3>API</h3>
          <div className="code-block"><code>curl -X POST -F "file=@yourfile.txt" -F "duration=100" {BACKEND_URL}/api/upload</code></div>
          <div className="code-block"><code>curl -X POST -F "url=https://example.com/file.zip" -F "duration=7" {BACKEND_URL}/api/upload</code></div>
        </div>
      </main>
      <footer className="footer" data-testid="footer">
        <span>GigaFile.nu Proxy</span><span className="dot">&middot;</span>
        <a href="https://t.me/fileshare300100_bot" target="_blank" rel="noopener noreferrer" data-testid="telegram-link">{t.tgBot}</a>
      </footer>
    </div>
  );
}

/* ─── Proxy Page ─── */
function ProxyPage() {
  const { t } = useLang();
  const [url, setUrl] = useState("");
  const handleDownload = () => {
    if (!url.trim()) return;
    window.open(`${API}/proxy?url=${encodeURIComponent(url.trim())}`, "_blank");
  };
  return (
    <div className="page" data-testid="proxy-page">
      <header className="header"><h1>{t.proxyTitle}</h1><p className="sub">{t.proxySub}</p></header>
      <main className="main">
        <div className="card" data-testid="proxy-card">
          <input data-testid="proxy-url-input" type="text" className="input" placeholder="https://XX.gigafile.nu/XXXX-..."
            value={url} onChange={(e) => setUrl(e.target.value)} />
          <button data-testid="proxy-download-btn" className="upload-btn" disabled={!url.trim()} onClick={handleDownload}>{t.download}</button>
        </div>
      </main>
    </div>
  );
}

/* ─── Nav ─── */
function Nav({ page, setPage }) {
  const { t } = useLang();
  return (
    <nav className="nav" data-testid="nav">
      <button data-testid="nav-upload" className={`nav-btn ${page === "upload" ? "active" : ""}`} onClick={() => setPage("upload")}>{t.upload}</button>
      <button data-testid="nav-proxy" className={`nav-btn ${page === "proxy" ? "active" : ""}`} onClick={() => setPage("proxy")}>{t.proxy}</button>
      <LangPicker />
    </nav>
  );
}

/* ─── App ─── */
function App() {
  const [page, setPage] = useState("upload");
  const [lang, setLangState] = useState(detectLang);

  const setLang = (code) => {
    setLangState(code);
    localStorage.setItem("gf_lang", code);
  };

  return (
    <LangContext.Provider value={{ lang, t: LANGS[lang], setLang }}>
      <div className="App" data-testid="app-root">
        <Nav page={page} setPage={setPage} />
        {page === "upload" ? <UploadPage /> : <ProxyPage />}
      </div>
    </LangContext.Provider>
  );
}

export default App;
