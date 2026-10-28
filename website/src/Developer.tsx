import { useEffect, useState } from "react";
import { Card, Tag } from "animal-island-ui";
import { ArrowUpRightIcon, DownloadIcon, LeafIcon } from "naive-icons";
import type { Language } from "./content";
import { GITHUB, formatBytes } from "./releases.mjs";

type SDK = {
  version: string;
  sourceUrl: string;
  release?: {
    url: string;
    asset: { url: string; name: string; bytes: number; sha256: string | null };
  };
};
const words = {
  "zh-CN": {
    kicker: "把你的想法，装进口袋",
    title: "你好，开发者。",
    intro:
      "为熟悉的随身听，写一个属于你的原生应用。X1000 SDK 把构建、绘图、触摸和打包串起来，让第一个小作品有路可走。",
    badge: "实验性源码开发套件",
    download: "下载 SDK 源码包",
    source: "浏览 SDK 源码",
    release: "发布与校验",
    profiles: "两种接入方式，同一套原始平台适配",
    callbackTitle: "快速起步：回调式应用",
    callbackText:
      "从三个模板开始，使用应用循环、触摸、基础画布和 SDL 预览。适合新的小工具与画布小游戏。",
    nativeTitle: "保留现有程序：原生服务层",
    nativeText:
      "原有 16 款应用采用 SDK 服务层，保留自己的主循环、界面和保存策略。可选网络、Unicode 字体、图片、大文件、进程与 PCM/FM 等 23 个模块。",
    serviceGuide: "原生服务与迁移说明",
    ready: "三个模板，从这里开始",
    minimal: "第一声问候",
    minimalText: "文字、返回按钮和退出清理，适合认识最小应用。",
    touch: "口袋计数器",
    touchText: "触摸按钮、本地设置和明确的存储状态，适合工具类应用。",
    canvas: "画布小实验",
    canvasText: "裁剪绘图、计时与动画，适合小游戏和自定义界面。",
    quick: "从第一行代码到安装包",
    environment:
      "在 Ubuntu 24.04 / WSL2 中，先按完整指南安装工具链并激活 Python 环境。以下命令在仓库或解压后的 SDK 根目录执行。",
    api: "小接口，复用现有平台适配",
    apiText:
      "C 接口提供应用循环、触摸事件、按钮、裁剪画布、ASCII 文字、RGB565 图片及受保护的资源/设置访问。设备端使用原始 Sony libc；Python 只在电脑上运行。",
    preview: "先在电脑里，让想法动起来",
    previewText:
      "同一份 C 应用支持 SDL2 交互预览，也能用事件脚本渲染 PNG。点击、拖动、计时和本地设置都可以离线检查。预览结果不代表实机验收。",
    limits: "第一版的明确边界",
    limitsText:
      "仅面向日版 NW-X1050 / NW-X1060 的 1.11 平台。回调式设置接口在所有权未知时拒绝读写；原生服务应用保留原有存储检查与格式。既有本地应用有用户测试通过报告，本次迁移检查为离线对照，不构成新的实机验收。",
    docs: "完整快速开始",
    reference: "接口参考",
    validation: "验证范围",
    publishing: "提交你的应用",
    archiveNote:
      "源码包不含 Sony 固件/库、ROM 或个人数据。不是可直接复制到播放器安装的应用包。",
    pending: "SDK 源码已开放；公开下载包尚未同步，请先查看源码。",
    counterAlt: "SDK 计数器电脑端真实渲染",
    canvasAlt: "SDK 动画示例电脑端真实渲染",
  },
  en: {
    kicker: "Put your idea in a pocket",
    title: "Hello, developer.",
    intro:
      "Make a native app for a familiar little player. The X1000 SDK brings building, drawing, touch and packaging together, so your first small project has a clear path.",
    badge: "Experimental source SDK",
    download: "Download SDK source",
    source: "Browse SDK source",
    release: "Release & checksum",
    profiles: "Two ways in, the original platform underneath",
    callbackTitle: "Start small: callback apps",
    callbackText:
      "Use the three starters, lifecycle, touch, basic canvas and SDL preview for new tools and canvas games.",
    nativeTitle: "Keep your app: native services",
    nativeText:
      "The 16 existing apps adopt SDK services while keeping their main loops, UI and save policies. Choose among 23 modules for networking, Unicode fonts, images, full-size files, processes and PCM/FM.",
    serviceGuide: "Native services & migration",
    ready: "Three small places to start",
    minimal: "A first hello",
    minimalText:
      "Text, a Back button and cleanup. Meet the smallest native app.",
    touch: "Pocket counter",
    touchText:
      "Touch controls, settings and explicit storage status for everyday tools.",
    canvas: "Canvas playground",
    canvasText:
      "Clipping, timing and motion for little games and custom interfaces.",
    quick: "From the first line to a package",
    environment:
      "On Ubuntu 24.04 / WSL2, follow the full guide to install the toolchain and activate Python first. Run these commands from the repository or extracted SDK root.",
    api: "A small API, existing platform adapters",
    apiText:
      "The C facade provides lifecycle, touch events, buttons, clipping, ASCII text, RGB565 images and guarded resource/settings IO. Device builds use Sony’s original libc. Python runs only on your computer.",
    preview: "Bring it to life on your computer",
    previewText:
      "The same C app supports an interactive SDL2 preview and scripted PNG rendering. Check taps, drags, timing and isolated settings offline. A preview does not qualify hardware behavior.",
    limits: "An explicit first-release boundary",
    limitsText:
      "Japanese NW-X1050 / NW-X1060, platform 1.11 only. Callback settings IO fails closed when ownership is unknown; native-service apps retain their original guards and formats. Previous local apps have a user test report; this migration uses offline comparisons, not new hardware acceptance.",
    docs: "Full quick start",
    reference: "API reference",
    validation: "Validation scope",
    publishing: "Submit an application",
    archiveNote:
      "The source bundle contains no Sony firmware/libraries, ROMs or personal data. It is not an application ZIP to install directly on a player.",
    pending:
      "SDK source is available; a public download has not synced yet. Browse the source to start.",
    counterAlt: "Actual PC-rendered SDK counter",
    canvasAlt: "Actual PC-rendered SDK canvas example",
  },
};
export function Developer({ lang }: { lang: Language }) {
  const t = words[lang];
  const [sdk, setSDK] = useState<SDK | null>(null);
  useEffect(() => {
    const abort = new AbortController();
    fetch(`${import.meta.env.BASE_URL}data/sdk.json`, { signal: abort.signal })
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then(setSDK)
      .catch(() => {});
    return () => abort.abort();
  }, []);
  const resource = (name: string, label: string) => (
    <a
      className="text-link"
      href={`${GITHUB}/blob/main/docs/sdk/${name}.md`}
      target="_blank"
      rel="noreferrer"
    >
      {label}
      <ArrowUpRightIcon size={16} />
    </a>
  );
  return (
    <section className="section shell page-section developer-page">
      <span className="kicker">
        <LeafIcon size={18} />
        {t.kicker}
      </span>
      <h1 className="page-title">{t.title}</h1>
      <p className="page-intro">{t.intro}</p>
      <Tag color="app-teal" variant="soft">
        {t.badge} · {sdk?.version || "API 1"}
      </Tag>
      <div className="sdk-actions">
        {sdk?.release ? (
          <a className="download-link" href={sdk.release.asset.url}>
            <DownloadIcon size={19} />
            {t.download}
            <small>{formatBytes(sdk.release.asset.bytes)}</small>
          </a>
        ) : (
          <p>{t.pending}</p>
        )}
        <a
          className="text-link"
          href={`${GITHUB}/tree/main/sdk`}
          target="_blank"
          rel="noreferrer"
        >
          {t.source}
          <ArrowUpRightIcon size={17} />
        </a>
        {sdk?.release && (
          <a
            className="text-link"
            href={sdk.release.url}
            target="_blank"
            rel="noreferrer"
          >
            {t.release}
            <ArrowUpRightIcon size={17} />
          </a>
        )}
      </div>
      <p className="sdk-note">{t.archiveNote}</p>
      {sdk?.release?.asset.sha256 && (
        <div className="sdk-checksum">
          <b>SHA-256</b>
          <code>{sdk.release.asset.sha256}</code>
        </div>
      )}
      <h2 className="sdk-section-title">{t.profiles}</h2>
      <div className="sdk-profile-grid">
        <Card>
          <h3>{t.callbackTitle}</h3>
          <p>{t.callbackText}</p>
          {resource("API", t.reference)}
        </Card>
        <Card>
          <h3>{t.nativeTitle}</h3>
          <p>{t.nativeText}</p>
          {resource("SERVICES", t.serviceGuide)}
        </Card>
      </div>
      <h2 className="sdk-section-title">{t.ready}</h2>
      <div className="guide-grid">
        {[
          ["minimal", t.minimal, t.minimalText],
          ["touch-ui", t.touch, t.touchText],
          ["canvas-game", t.canvas, t.canvasText],
        ].map(([id, title, text], i) => (
          <Card className="guide-card" key={id}>
            <span className="step-number">0{i + 1}</span>
            <h3>{title}</h3>
            <p>{text}</p>
            <a
              className="text-link"
              href={`${GITHUB}/tree/main/sdk/templates/${id}`}
              target="_blank"
              rel="noreferrer"
            >
              {id}
              <ArrowUpRightIcon size={16} />
            </a>
          </Card>
        ))}
      </div>
      <div className="sdk-preview-row">
        <Card>
          <img
            src={`${import.meta.env.BASE_URL}media/sdk-counter.png`}
            alt={t.counterAlt}
          />
        </Card>
        <Card>
          <img
            src={`${import.meta.env.BASE_URL}media/sdk-canvas.png`}
            alt={t.canvasAlt}
          />
        </Card>
        <div>
          <span className="kicker">SAME C SOURCE</span>
          <h2>{t.preview}</h2>
          <p>{t.previewText}</p>
        </div>
      </div>
      <h2 className="sdk-section-title">{t.quick}</h2>
      <p>{t.environment}</p>
      <pre className="sdk-code">
        <code>{`python tools/sdk.py setup\npython tools/sdk.py doctor\npython tools/sdk.py new my-counter --template touch-ui\npython tools/sdk.py preview my-counter --data\npython tools/sdk.py build my-counter --output work/my-counter-build\npython tools/verify_app_package.py work/my-counter-build/package\npython tools/sdk.py package my-counter --from-package work/my-counter-build/package`}</code>
      </pre>
      <Card className="sdk-api">
        <h2>{t.api}</h2>
        <p>{t.apiText}</p>
        <pre className="sdk-code">
          <code>{`#include <x1000/app.h>\n#include <x1000/storage.h>\n\nxw_fill(app, (xw_rect){16, 90, 208, 50}, xw_rgb(54, 135, 119));\nxw_text(app, 24, 106, "Hello, Walkman!", 1, xw_rgb(255, 253, 245));\nxw_redraw(app);`}</code>
        </pre>
      </Card>
      <div className="risk-box">
        <div>
          <h3>{t.limits}</h3>
          <p>{t.limitsText}</p>
        </div>
      </div>
      <div className="guide-resources">
        {resource("README", t.docs)}
        {resource("API", t.reference)}
        {resource("VALIDATION", t.validation)}
        {resource("PUBLISHING", t.publishing)}
      </div>
    </section>
  );
}
