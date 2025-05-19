import { getCurrentWebview } from '@tauri-apps/api/webview';

import Titlebar from '~view/Titlebar';
import Ask from '~view/Ask';
import Settings from '~view/Settings';

const viewMap = {
  titlebar: <Titlebar />,
  ask: <Ask />,
  settings: <Settings />,
};

export default function App() {
  const webview = getCurrentWebview();
  return viewMap[webview.label as keyof typeof viewMap] || null;
}
