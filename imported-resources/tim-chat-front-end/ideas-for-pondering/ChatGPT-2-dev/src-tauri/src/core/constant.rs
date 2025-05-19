pub static TITLEBAR_HEIGHT: f64 = 28.0;
pub static ASK_HEIGHT: f64 = 120.0;

pub static WINDOW_SETTINGS: &str = "settings";

pub static INIT_SCRIPT: &str = r#"
window.addEventListener('DOMContentLoaded', function() {
    function handleUrlChange() {
        const url = window.location.href;
        if (url !== 'about:blank') {
            console.log('URL changed:', url);
            window.__TAURI__.webviewWindow.WebviewWindow.getByLabel('titlebar').emit('navigation:change', { url });
        }
    }

    function handleLinkClick(event) {
        const target = event.target;
        if (target.tagName === 'A' && target.target && target.target !== '_blank') {
            target.target = '_blank';
        }
    }

    document.addEventListener('click', handleLinkClick, true);
    window.addEventListener('popstate', handleUrlChange);
    window.addEventListener('pushState', handleUrlChange);
    window.addEventListener('replaceState', handleUrlChange);

    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = function() {
        originalPushState.apply(this, arguments);
        console.log('pushState called');
        handleUrlChange();
    };

    history.replaceState = function() {
        originalReplaceState.apply(this, arguments);
        console.log('replaceState called');
        handleUrlChange();
    };

    handleUrlChange();
});
"#;
