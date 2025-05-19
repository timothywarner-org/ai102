import { useEffect, useState } from 'react';
import { Window } from '@tauri-apps/api/window';

import WindowClose from '~icons/WindowClose';
import WindowMaximize from '~icons/WindowMaximize';
import WindowMinimize from '~icons/WindowMinimize';
import WindowRestore from '~/icons/WindowRestore';

export default function WinTitlebar() {
  const [isMax, setMax] = useState(false);

  useEffect(() => {
    (async () => {
      const win = Window.getByLabel('core');
      const max = await win?.isMaximized();
      setMax(!!max);
    })()
  }, [])

  const handleToggle = async () => {
    const win = Window.getByLabel('core');
    await win?.toggleMaximize();
    setMax(!isMax);
  }

  const handleMinimize = () => {
    const win = Window.getByLabel('core');
    win?.minimize();
  };

  const handleClose = () => {
    const win = Window.getByLabel('core');
    win?.close();
  }

  return (
    <div className="flex items-center gap-1">
      <WindowMinimize size={20} className="p-0" onClick={handleMinimize} />
      {isMax
        ? <WindowRestore size={20} className="p-0" onClick={handleToggle} />
        : <WindowMaximize size={20} className="p-0" onClick={handleToggle} />}
      <WindowClose size={20} className="p-0" onClick={handleClose} />
    </div>
  )
}