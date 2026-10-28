import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Button,
  Card,
  Checkbox,
  Drawer,
  Input,
  Select,
  Tag,
} from "animal-island-ui";
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  DownloadIcon,
  FlowerIcon,
  GlobeIcon,
  HeadphonesIcon,
  LeafIcon,
  MusicIcon,
  SearchIcon,
  ShieldIcon,
  SparklesIcon,
  SunIcon,
} from "naive-icons";
import "animal-island-ui/style";
import "./style.css";
import { Developer } from "./Developer";
import {
  appDetails,
  changesZh,
  copy,
  guidePath,
  type Language,
} from "./content";
import {
  appAsset,
  firmwareAsset,
  formatBytes,
  GITHUB,
  sanitizeReleases,
} from "./releases.mjs";

type AppInfo = {
  id: string;
  title: string;
  summary: string;
  description: string;
  changes: string;
  version: string;
  channel: string;
};
type Asset = {
  name: string;
  size: number;
  browser_download_url: string;
  digest: string | null;
};
type Release = {
  tag_name: string;
  name: string;
  prerelease: boolean;
  published_at: string;
  html_url: string;
  assets: Asset[];
};
type Page = "home" | "firmware" | "apps" | "guide" | "developer";
const base = import.meta.env.BASE_URL;
const media = (name: string) => `${base}media/${name}`;
const doc = (name: string) => `${GITHUB}/blob/main/${name}`;
const order = [
  "qqmusic",
  "fm-radio",
  "ebook",
  "dictionary",
  "gbc",
  "tamagotchi-id",
  "terminal",
  "language",
  "store",
  "device-info",
  "graphics-demo",
  "key-check",
  "diagnostics",
  "hello",
];
function readRoute(): Page {
  const route = location.hash.slice(1).split("?")[0];
  return ["firmware", "apps", "guide", "developer"].includes(route)
    ? (route as Page)
    : "home";
}
function initialLanguage(): Language {
  const query = new URLSearchParams(location.search).get("lang");
  if (query === "en" || query === "zh-CN") return query;
  try {
    const saved = localStorage.getItem("x1000-language");
    if (saved === "en" || saved === "zh-CN") return saved;
  } catch {
    /* Private browsing may disable storage. */
  }
  return navigator.language.startsWith("zh") ? "zh-CN" : "en";
}
function Link({
  href,
  children,
  className = "",
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <a
      className={`text-link ${className}`}
      href={href}
      target="_blank"
      rel="noreferrer"
    >
      {children}
      <ArrowUpRightIcon size={17} />
    </a>
  );
}
function App() {
  const [lang, setLang] = useState<Language>(initialLanguage);
  const [page, setPage] = useState<Page>(readRoute);
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [catalogError, setCatalogError] = useState(false);
  const [releases, setReleases] = useState<Release[]>([]);
  const [selectedTag, setSelectedTag] = useState("");
  const [releaseState, setReleaseState] = useState<
    "loading" | "live" | "snapshot" | "error"
  >("loading");
  const [refreshKey, setRefreshKey] = useState(0);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState("curated");
  const [model, setModel] = useState("");
  const [ack, setAck] = useState<Array<string | number>>([]);
  const [detail, setDetail] = useState<AppInfo | null>(null);
  const [hashStatus, setHashStatus] = useState("");
  const t = copy[lang];
  const selected =
    releases.find((r) => r.tag_name === selectedTag) || releases[0];
  const canDownload =
    ["x1050", "x1060"].includes(model) && ack.includes("risk");
  useEffect(() => {
    const onHash = () => {
      setPage(readRoute());
      setDetail(null);
      window.scrollTo({ top: 0, behavior: "instant" });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = `${page === "home" ? "X1000 Island" : t[page] + " · X1000 Island"}${lang === "zh-CN" ? " · 给 Walkman 一点新可能" : " · A world in your pocket"}`;
    try {
      localStorage.setItem("x1000-language", lang);
    } catch {
      /* Optional persistence. */
    }
    const url = new URL(location.href);
    url.searchParams.set("lang", lang);
    history.replaceState(null, "", url);
  }, [lang, page, t]);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${base}data/catalog.json`, { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((data) => setApps(data.apps))
      .catch(() => {
        if (!controller.signal.aborted) setCatalogError(true);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let live = false;
    setReleaseState("loading");
    const snapshot = fetch(`${base}data/releases.json`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((data) => {
        if (!live && !controller.signal.aborted) {
          setReleases(sanitizeReleases(data.releases));
          setReleaseState("snapshot");
        }
      })
      .catch(() => {});
    const timer = setTimeout(() => controller.abort(), 15000);
    fetch(
      `https://api.github.com/repos/vicliu624/sony-nw-x1000-series-cfw/releases?per_page=30`,
      {
        signal: controller.signal,
        headers: { Accept: "application/vnd.github+json" },
      },
    )
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((data) => {
        const clean = sanitizeReleases(data);
        live = true;
        setReleases(clean);
        setReleaseState("live");
      })
      .catch(async () => {
        await snapshot;
        if (!live)
          setReleaseState((state) => (state === "loading" ? "error" : state));
      })
      .finally(() => clearTimeout(timer));
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [refreshKey]);
  useEffect(() => {
    setHashStatus("");
  }, [detail, selectedTag, lang]);
  const title = (app: AppInfo) =>
    lang === "zh-CN" ? appDetails[app.id]?.title || app.title : app.title;
  const summary = (app: AppInfo) =>
    lang === "zh-CN" ? appDetails[app.id]?.summary || app.summary : app.summary;
  const go = (next: Page) => {
    location.hash = next === "home" ? "" : next;
  };
  const sortedApps = [...apps].sort(
    (a, b) => order.indexOf(a.id) - order.indexOf(b.id),
  );
  const visibleApps = sortedApps
    .filter(
      (app) =>
        (category === "all" || appDetails[app.id]?.category === category) &&
        `${app.title} ${app.id} ${app.summary} ${app.description} ${appDetails[app.id]?.title} ${appDetails[app.id]?.summary}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()),
    )
    .sort((a, b) =>
      sort === "alphabetical" ? a.title.localeCompare(b.title) : 0,
    );
  async function copyHash(asset: Asset) {
    try {
      await navigator.clipboard.writeText(asset.digest!.slice(7));
      setHashStatus(t.copied);
    } catch {
      setHashStatus(t.copyFailed);
    }
  }
  function FileCard({
    asset,
    name,
    description,
    gated = false,
  }: {
    asset?: Asset;
    name: string;
    description: string;
    gated?: boolean;
  }) {
    const enabled = asset && (!gated || canDownload);
    return (
      <Card className="file-card">
        <div className="file-heading">
          <span className="file-symbol">
            <DownloadIcon size={24} />
          </span>
          <div>
            <h3>{name}</h3>
            {asset && <small>{formatBytes(asset.size)} · ZIP</small>}
          </div>
        </div>
        <p>{description}</p>
        {asset && <div className="file-name">{asset.name}</div>}
        {enabled ? (
          <a className="download-link" href={asset.browser_download_url}>
            <DownloadIcon size={18} />
            {t.download}
          </a>
        ) : (
          <Button block disabled>
            {asset ? t.selectFirst : t.unavailable}
          </Button>
        )}
        {asset && (
          <div className="hash-area">
            {asset.digest ? (
              <>
                <span>SHA-256</span>
                <code>{asset.digest.slice(7)}</code>
                <Button
                  type="text"
                  size="small"
                  onClick={() => copyHash(asset)}
                >
                  {t.copyHash}
                </Button>
              </>
            ) : (
              <small>{t.noDigest}</small>
            )}
          </div>
        )}
      </Card>
    );
  }
  function ReleasePicker() {
    return (
      <div className="release-picker">
        <label id={`release-label-${page}`}>{t.release}</label>
        <Select
          aria-labelledby={`release-label-${page}`}
          value={selected?.tag_name || ""}
          onChange={setSelectedTag}
          disabled={!releases.length}
          placeholder={t.loading}
          options={releases.map((r) => ({
            key: r.tag_name,
            label: `${r.tag_name}${r.prerelease ? (lang === "zh-CN" ? " · 实验版" : " · Prerelease") : ""}`,
          }))}
        />
      </div>
    );
  }
  function ReleaseStatus() {
    return (
      <div className="release-status" role="status">
        <span
          className={`status-dot ${releaseState === "live" ? "online" : ""}`}
        />
        {releaseState === "loading"
          ? t.loading
          : releaseState === "live"
            ? t.live
            : releaseState === "snapshot"
              ? t.snapshot
              : t.noRelease}
        <Button
          type="text"
          size="small"
          onClick={() => setRefreshKey((k) => k + 1)}
        >
          {t.refresh}
        </Button>
      </div>
    );
  }
  function ReleaseLinks() {
    return (
      <div className="release-links">
        {selected?.assets
          .filter((a) =>
            ["SHA256SUMS", "release-manifest.json"].includes(a.name),
          )
          .map((a) => (
            <Link key={a.name} href={a.browser_download_url}>
              {a.name === "SHA256SUMS" ? t.checksum : t.manifest}
            </Link>
          ))}
        <Link href={selected?.html_url || `${GITHUB}/releases`}>{t.notes}</Link>
      </div>
    );
  }
  const detailAsset = detail ? appAsset(selected, detail.id) : undefined;
  return (
    <>
      <a
        href="#main"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        {lang === "zh-CN" ? "跳到主要内容" : "Skip to content"}
      </a>
      <header className="header">
        <div className="nav-shell">
          <a className="brand" href="#" aria-label="X1000 Island">
            <span className="brand-icon">
              <HeadphonesIcon size={26} />
            </span>
            <span>
              X1000 <b>Island</b>
              <small>WALKMAN HOMEBREW</small>
            </span>
          </a>
          <nav aria-label={lang === "zh-CN" ? "主导航" : "Main navigation"}>
            {(["home", "firmware", "apps", "guide", "developer"] as Page[]).map(
              (item) => (
                <a
                  key={item}
                  className={page === item ? "active" : ""}
                  href={item === "home" ? "#" : `#${item}`}
                  aria-current={page === item ? "page" : undefined}
                >
                  {t[item]}
                </a>
              ),
            )}
          </nav>
          <div className="nav-actions">
            <Button
              size="small"
              type="text"
              icon={<GlobeIcon size={18} />}
              aria-label={t.languageLabel}
              onClick={() => setLang(lang === "zh-CN" ? "en" : "zh-CN")}
            >
              {lang === "zh-CN" ? "EN" : "中文"}
            </Button>
            <a
              className="github-link"
              href={GITHUB}
              target="_blank"
              rel="noreferrer"
            >
              GitHub
              <ArrowUpRightIcon size={16} />
            </a>
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {page === "developer" && <Developer lang={lang} />}
        {page === "home" && (
          <>
            <section className="hero shell">
              <div className="hero-copy">
                <div className="eyebrow">
                  <LeafIcon size={19} />
                  {t.eyebrow}
                </div>
                <h1>
                  {t.hero1}
                  <br />
                  <span>{t.hero2}</span>
                </h1>
                <p className="hero-intro">{t.intro}</p>
                <div className="hero-actions">
                  <Button
                    type="primary"
                    size="large"
                    icon={<SparklesIcon size={20} />}
                    onClick={() => go("apps")}
                  >
                    {t.explore}
                  </Button>
                  <Button size="large" onClick={() => go("firmware")}>
                    {t.getFirmware}
                    <ArrowRightIcon size={18} />
                  </Button>
                </div>
                <div className="compatibility">
                  <ShieldIcon size={17} />
                  {t.compatible}
                </div>
              </div>
              <div className="hero-art" aria-label={t.deviceScreen} role="img">
                <div className="art-orbit orbit-one" />
                <div className="art-orbit orbit-two" />
                <div className="art-sun">
                  <SunIcon size={48} />
                </div>
                <span className="art-flower">
                  <FlowerIcon size={40} />
                </span>
                <span className="floating-note">
                  <MusicIcon size={28} />
                </span>
                <div className="device">
                  <span className="device-wordmark">WALKMAN</span>
                  <div className="device-screen">
                    <div className="screen-top">
                      <span>12:00</span>
                      <span>NW-X1000</span>
                    </div>
                    <span className="screen-greeting">
                      Hello, little world.
                    </span>
                    <div className="screen-landscape">
                      <div className="screen-sun" />
                      <div className="hill hill-back" />
                      <div className="hill hill-front" />
                      <div className="screen-house">
                        <span />
                      </div>
                      <span className="screen-flower">
                        <FlowerIcon size={32} />
                      </span>
                    </div>
                    <div className="screen-player">
                      <span className="mini-album">
                        <MusicIcon size={21} />
                      </span>
                      <div>
                        <b>A little island</b>
                        <small>Your pocket soundtrack</small>
                      </div>
                      <HeadphonesIcon size={22} />
                    </div>
                    <div className="screen-apps">
                      {["qqmusic", "fm-radio", "ebook", "gbc"].map((id) => (
                        <img key={id} src={media(`apps/${id}.svg`)} alt="" />
                      ))}
                    </div>
                  </div>
                  <div className="device-home">
                    <span />
                  </div>
                </div>
                <div className="art-label">
                  <span className="label-dot" />
                  {t.islandNote}
                  <small>{t.islandCaption}</small>
                </div>
              </div>
            </section>
            <div className="island-strip shell">
              <span>
                <span className="status-dot online" />
                {t.experimental}
              </span>
              <div>
                <b>{apps.length || "14"}</b>
                {t.statApps}
              </div>
              <div>
                <b>4</b>
                {t.statLanguages}
              </div>
              <div>
                <b>1.11</b>
                {t.statPlatform}
              </div>
            </div>
            <section className="section shell">
              <div className="section-head">
                <div>
                  <span className="kicker">{t.featured}</span>
                  <h2>{t.pickTitle}</h2>
                  <p>{t.pickSub}</p>
                </div>
                <a className="text-link" href="#apps">
                  {t.allApps}
                  <ArrowRightIcon size={19} />
                </a>
              </div>
              <div className="featured-grid">
                {["qqmusic", "fm-radio", "ebook"].map((id, i) => {
                  const app = apps.find((a) => a.id === id);
                  return (
                    <Card
                      key={id}
                      color={
                        (["app-green", "app-orange", "app-teal"] as const)[i]
                      }
                      className="feature-card"
                    >
                      <div className="feature-visual">
                        <span className="feature-no">0{i + 1}</span>
                        <img src={media(`apps/${id}.svg`)} alt="" />
                        <span className="feature-spark">
                          <SparklesIcon size={23} />
                        </span>
                      </div>
                      <Tag
                        className="site-tag"
                        variant="soft"
                        color={
                          (["app-green", "app-orange", "app-teal"] as const)[i]
                        }
                      >
                        {i === 0 || i === 1 ? t.music : t.reading}
                      </Tag>
                      <h3>
                        {app
                          ? title(app)
                          : id === "ebook"
                            ? lang === "zh-CN"
                              ? "口袋阅读"
                              : "EBook"
                            : id === "qqmusic"
                              ? "QQ Music"
                              : "Pocket FM"}
                      </h3>
                      <p>{[t.qqText, t.fmText, t.ebookText][i]}</p>
                      <Button
                        type="text"
                        onClick={() => {
                          if (app) setDetail(app);
                        }}
                        disabled={!app}
                      >
                        {t.details}
                        <ArrowRightIcon size={18} />
                      </Button>
                    </Card>
                  );
                })}
              </div>
            </section>
            <section className="story-section shell">
              <div className="story-image">
                <img
                  src={media("launcher-market.png")}
                  alt={
                    lang === "zh-CN"
                      ? "原生启动器与集市渲染预览"
                      : "Native-rendered launcher and market preview"
                  }
                  loading="lazy"
                />
                <span>FROM THE NATIVE RENDERER</span>
              </div>
              <div className="story-copy">
                <span className="kicker">BUILT FOR A LITTLE SCREEN</span>
                <h2>
                  {lang === "zh-CN"
                    ? "熟悉的设备，\n不一样的日常。"
                    : "A familiar player.\nA fresh little routine."}
                </h2>
                <p>
                  {lang === "zh-CN"
                    ? "保留原有系统的熟悉感，从一个 Homebrew 入口，打开原生应用的世界。启动器、集市与应用文件，都有各自清晰的位置。"
                    : "Keep the familiar Sony experience. A single Homebrew entry opens a world of native apps, with a launcher and market on visible user storage."}
                </p>
                <p className="evidence-note">{t.evidence}</p>
                <Link href={doc("docs/apps/STORE.md")}>{t.viewGuide}</Link>
              </div>
            </section>
            <section className="home-cta shell">
              <div>
                <LeafIcon size={28} />
                <h2>
                  {lang === "zh-CN"
                    ? "下一段故事，从这里开始。"
                    : "Your next chapter starts here."}
                </h2>
                <p>{t.compatible}</p>
              </div>
              <Button
                type="primary"
                size="large"
                icon={<DownloadIcon size={20} />}
                onClick={() => go("firmware")}
              >
                {t.getFirmware}
              </Button>
            </section>
          </>
        )}
        {page === "firmware" && (
          <section className="section shell page-section">
            <span className="kicker">{t.downloadKicker}</span>
            <h1 className="page-title">{t.downloadTitle}</h1>
            <p className="page-intro">{t.downloadIntro}</p>
            <ReleaseStatus />
            <Card className="download-selector">
              <div>
                <label id="model-label">{t.model}</label>
                <Select
                  aria-labelledby="model-label"
                  value={model}
                  onChange={(value) => {
                    setModel(value);
                    setAck([]);
                  }}
                  placeholder={t.chooseModel}
                  options={[
                    { key: "x1060", label: t.x1060 },
                    { key: "x1050", label: t.x1050 },
                    { key: "other", label: t.other },
                  ]}
                />
              </div>
              <ReleasePicker />
            </Card>
            {model === "other" ? (
              <div className="risk-box" role="alert">
                <ShieldIcon size={24} />
                <p>{t.unsupported}</p>
              </div>
            ) : (
              <div className="risk-box">
                <ShieldIcon size={26} />
                <div>
                  <h3>{t.risk}</h3>
                  <p>{t.riskText}</p>
                  <Link href={doc("docs/STATUS.md")}>{t.statusLink}</Link>
                  <Checkbox
                    className="risk-ack"
                    disabled={!["x1050", "x1060"].includes(model)}
                    options={[{ value: "risk", label: t.acknowledge }]}
                    value={ack}
                    onChange={setAck}
                  />
                </div>
              </div>
            )}
            <div className="download-grid">
              <FileCard
                asset={firmwareAsset(selected, "firmware")}
                name={t.firmwareName}
                description={t.firmwareDesc}
                gated
              />
              <FileCard
                asset={firmwareAsset(selected, "player-setup")}
                name={t.setupName}
                description={t.setupDesc}
                gated
              />
            </div>
            <p role="status" className="hash-status">
              {hashStatus}
            </p>
            <ReleaseLinks />
            <div className="download-instructions">
              <h2>{t.installation}</h2>
              <ol>
                <li>{t.step1Text}</li>
                <li>{t.step2Text}</li>
                <li>
                  {lang === "zh-CN"
                    ? "进入 Homebrew 菜单前，先将播放器配置包中的文件放到可见用户存储。完整安装流程以项目说明为准。"
                    : "Copy the player-setup files to visible user storage before entering Homebrew. Follow the project documentation for the complete installation procedure."}
                </li>
              </ol>
              <Link href={doc("docs/RELEASES.md")}>{t.releaseLink}</Link>
            </div>
          </section>
        )}
        {page === "apps" && (
          <section className="section shell page-section">
            <span className="kicker">{t.marketKicker}</span>
            <div className="market-heading">
              <div>
                <h1 className="page-title">
                  {t.marketTitle}
                  <FlowerIcon size={40} />
                </h1>
                <p className="page-intro">{t.marketIntro}</p>
              </div>
              <Tag className="site-tag" color="app-teal" variant="soft">
                {apps.length} OPEN-SOURCE APPS
              </Tag>
            </div>
            <div className="market-controls">
              <div className="search-field">
                <Input
                  aria-label={t.search}
                  placeholder={t.search}
                  prefix={<SearchIcon size={20} />}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  allowClear
                  onClear={() => setQuery("")}
                  clearAriaLabel={t.reset}
                />
              </div>
              <ReleasePicker />
              <div className="sort-picker">
                <Select
                  aria-label={t.sort}
                  value={sort}
                  onChange={setSort}
                  options={[
                    { key: "curated", label: t.curated },
                    { key: "alphabetical", label: t.alphabetical },
                  ]}
                />
              </div>
            </div>
            <div
              className="category-tabs"
              role="group"
              aria-label={lang === "zh-CN" ? "应用分类" : "App categories"}
            >
              {(["all", "music", "reading", "games", "tools"] as const).map(
                (c) => (
                  <Button
                    key={c}
                    type={category === c ? "primary" : "text"}
                    aria-pressed={category === c}
                    onClick={() => setCategory(c)}
                  >
                    {t[c]}
                  </Button>
                ),
              )}
            </div>
            <div className="market-meta">
              <span role="status">
                {visibleApps.length} {t.results}
              </span>
              <span>{t.offline}</span>
            </div>
            {catalogError && (
              <p role="alert">
                {lang === "zh-CN"
                  ? "应用目录读取失败，请刷新页面或访问源码。"
                  : "Could not load the app catalog. Reload or visit the source repository."}{" "}
                <Link href={doc("runtime/apps")}>{t.source}</Link>
              </p>
            )}
            {!visibleApps.length && !catalogError && (
              <Card className="empty-state">
                <SearchIcon size={40} />
                <h2>{t.empty}</h2>
                <p>{t.emptySub}</p>
                <Button
                  onClick={() => {
                    setCategory("all");
                    setQuery("");
                  }}
                >
                  {t.reset}
                </Button>
              </Card>
            )}
            <div className="app-grid">
              {visibleApps.map((app) => (
                <Card className="app-card" key={app.id}>
                  <div className="app-card-top">
                    <img
                      src={media(`apps/${app.id}.svg`)}
                      alt=""
                      loading="lazy"
                    />
                    <Tag
                      className="site-tag"
                      color={
                        appAsset(selected, app.id) ? "app-green" : "app-orange"
                      }
                      variant="soft"
                      size="small"
                    >
                      {appAsset(selected, app.id) ? t.available : t.sourceOnly}
                    </Tag>
                  </div>
                  <h3>{title(app)}</h3>
                  <p>{summary(app)}</p>
                  <div className="app-card-bottom">
                    <small>
                      {appAsset(selected, app.id)?.version || app.version}
                    </small>
                    <Button
                      size="small"
                      type="text"
                      aria-label={`${t.details} · ${title(app)}`}
                      onClick={() => setDetail(app)}
                    >
                      {t.details}
                      <ArrowRightIcon size={17} />
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
            <ReleaseStatus />
          </section>
        )}
        {page === "guide" && (
          <section className="section shell page-section">
            <span className="kicker">{t.guideKicker}</span>
            <h1 className="page-title">{t.guideTitle}</h1>
            <p className="page-intro">{t.compatible}</p>
            <div className="guide-grid">
              {[1, 2, 3].map((n) => (
                <Card key={n} className="guide-card">
                  <span className="step-number">0{n}</span>
                  <h2>{t[`step${n}` as "step1" | "step2" | "step3"]}</h2>
                  <p>
                    {
                      t[
                        `step${n}Text` as
                          | "step1Text"
                          | "step2Text"
                          | "step3Text"
                      ]
                    }
                  </p>
                  <Link
                    href={doc(
                      [
                        "docs/STATUS.md",
                        "docs/RELEASES.md",
                        "docs/apps/STORE.md",
                      ][n - 1],
                    )}
                  >
                    {[t.statusLink, t.releaseLink, t.viewGuide][n - 1]}
                  </Link>
                </Card>
              ))}
            </div>
            <div className="risk-box">
              <ShieldIcon size={28} />
              <p>{t.riskText}</p>
            </div>
            <div className="guide-resources">
              <Link href={doc("docs/APP_DEVELOPMENT.md")}>
                {t.developerLink}
              </Link>
              <Link href={doc("docs/KNOWLEDGE.md")}>
                {lang === "zh-CN"
                  ? "平台知识与研究交接"
                  : "Platform knowledge & research"}
              </Link>
              <Link href={doc("THIRD_PARTY.md")}>
                {lang === "zh-CN"
                  ? "开源许可与致谢"
                  : "Licenses & acknowledgments"}
              </Link>
            </div>
          </section>
        )}
      </main>
      <footer className="footer">
        <div className="shell footer-main">
          <div>
            <a className="footer-brand" href="#">
              <HeadphonesIcon size={24} />
              X1000 Island
            </a>
            <p>{t.footerLine}</p>
            <small>{t.footerNote}</small>
          </div>
          <div className="footer-links">
            <a href="#firmware">{t.firmware}</a>
            <a href="#apps">{t.apps}</a>
            <Link href={GITHUB}>{t.source}</Link>
          </div>
        </div>
        <div className="shell footer-bottom">
          <span>Made with care, for the music we keep.</span>
          <a
            href="https://github.com/guokaigdg/animal-island-ui"
            target="_blank"
            rel="noreferrer"
          >
            <LeafIcon size={16} />
            {t.credits}
          </a>
        </div>
      </footer>
      <Drawer
        className="app-drawer"
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail ? title(detail) : ""}
        width="min(620px, 100vw)"
        pushBackground={false}
        footer={
          <Button block onClick={() => setDetail(null)}>
            {t.close}
          </Button>
        }
      >
        {detail && (
          <div className="app-detail">
            <div className="detail-heading">
              <img src={media(`apps/${detail.id}.svg`)} alt="" />
              <div>
                <Tag className="site-tag" color="app-orange" variant="soft">
                  {t.experimental}
                </Tag>
                <p>{summary(detail)}</p>
              </div>
            </div>
            <h3>{t.appAbout}</h3>
            <p>
              {lang === "zh-CN"
                ? appDetails[detail.id]?.description || detail.description
                : detail.description}
            </p>
            <dl>
              <dt>{t.sourceVersion}</dt>
              <dd>{detail.version}</dd>
              <dt>{t.publishedVersion}</dt>
              <dd>{detailAsset?.version || "—"}</dd>
              <dt>{t.release}</dt>
              <dd>{selected?.tag_name || "—"}</dd>
            </dl>
            <h3>{t.appChanges}</h3>
            <p>
              {lang === "zh-CN"
                ? changesZh[detail.id] || detail.changes
                : detail.changes}
            </p>
            <Link href={doc(guidePath(detail.id))}>{t.viewGuide}</Link>
            <h3>{t.installation}</h3>
            <p>{t.installText}</p>
            {detailAsset ? (
              <FileCard
                asset={detailAsset}
                name={t.package}
                description={`${selected?.tag_name} · ${detailAsset.version}`}
              />
            ) : (
              <p>{t.noAppDownload}</p>
            )}
            <p role="status">{hashStatus}</p>
            <ReleaseLinks />
            <div className="detail-source">
              <Link href={doc(`runtime/apps/${detail.id}`)}>{t.source}</Link>
            </div>
          </div>
        )}
      </Drawer>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
