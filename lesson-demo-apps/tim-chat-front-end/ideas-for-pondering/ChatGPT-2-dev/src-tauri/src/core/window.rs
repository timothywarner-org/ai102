use tauri::{command, AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

use crate::core::constant::WINDOW_SETTINGS;

#[command]
pub fn open_settings(app: AppHandle) {
  match app.get_webview_window(WINDOW_SETTINGS) {
    Some(window) => {
      window.show().unwrap();
    }
    None => {
      WebviewWindowBuilder::new(&app, WINDOW_SETTINGS, WebviewUrl::App("index.html".into()))
        .build()
        .unwrap();
    }
  }
}
