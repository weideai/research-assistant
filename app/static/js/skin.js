/* R/LAB 皮肤切换器 —— 三套皮肤（swiss 经典 / ide-light 浅色 / ide-dark 深色）。
 *
 * 本脚本在 <head> 中同步加载（项目 CSP 为 script-src 'self'，禁止内联脚本），
 * 因此在 <body> 渲染前就会把 data-skin 写到 <html> 上，避免换肤闪烁（FOUC）。
 * 皮肤选择仅保存在浏览器 localStorage，不写入任何科研数据。
 */
(function () {
  "use strict";

  var STORAGE_KEY = "rlab-skin-v2";
  var DEFAULT_SKIN = "ide-light";

  /* 皮肤注册表：label 用于界面展示，themeColor 同步浏览器地址栏主题色 */
  var SKINS = {
    "ide-light": { label: "科研浅色", themeColor: "#f5f7fb" },
    "ide-dark": { label: "科研深色", themeColor: "#0b0e14" },
    "swiss": { label: "经典 Swiss", themeColor: "#f2f2ef" }
  };

  /* 读取已保存的皮肤；localStorage 不可用（隐私模式等）时降级为默认皮肤 */
  function readSavedSkin() {
    try {
      var saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && Object.prototype.hasOwnProperty.call(SKINS, saved)) {
        return saved;
      }
    } catch (err) {
      /* 读取失败时保持默认，不影响页面使用 */
    }
    return DEFAULT_SKIN;
  }

  /* 应用皮肤：写 data-skin、同步 theme-color、持久化并刷新切换器选中态 */
  function applySkin(skin, persist) {
    if (!Object.prototype.hasOwnProperty.call(SKINS, skin)) {
      skin = DEFAULT_SKIN;
    }
    var root = document.documentElement;
    if (skin === DEFAULT_SKIN) {
      root.removeAttribute("data-skin"); /* 默认皮肤不挂属性，完全走 tokens.css */
    } else {
      root.setAttribute("data-skin", skin);
    }

    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute("content", SKINS[skin].themeColor);
    }

    if (persist) {
      try {
        window.localStorage.setItem(STORAGE_KEY, skin);
      } catch (err) {
        /* 持久化失败仅意味着下次打开回到默认皮肤 */
      }
    }

    /* 切换器 UI 可能尚未渲染（head 阶段），存在才更新；页面可能有多处当前皮肤标签 */
    var labels = document.querySelectorAll("[data-skin-current]");
    for (var j = 0; j < labels.length; j++) {
      labels[j].textContent = SKINS[skin].label;
    }
    var choices = document.querySelectorAll("[data-skin-choice]");
    for (var i = 0; i < choices.length; i++) {
      choices[i].setAttribute(
        "aria-checked",
        choices[i].getAttribute("data-skin-choice") === skin ? "true" : "false"
      );
    }
  }

  /* 首帧前立即应用已保存的皮肤 */
  applySkin(readSavedSkin(), false);

  /* DOM 就绪后绑定切换器交互 */
  document.addEventListener("DOMContentLoaded", function () {
    var choices = document.querySelectorAll("[data-skin-choice]");
    for (var i = 0; i < choices.length; i++) {
      choices[i].addEventListener("click", function () {
        applySkin(this.getAttribute("data-skin-choice"), true);
        /* 选择后收起 details 菜单 */
        var switcher = this.closest("details");
        if (switcher) {
          switcher.removeAttribute("open");
        }
      });
    }
    /* head 阶段 UI 未渲染，这里补一次选中态同步 */
    applySkin(readSavedSkin(), false);
  });
})();
