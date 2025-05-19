/**
 * @name ask.js
 * @version 0.1.0
 * @url https://github.com/lencx/ChatGPT/tree/main/scripts/ask.js
 */

class ChatAsk {
  static sync(message) {
    const inputElement = document.querySelector('textarea');
    if (inputElement) {
      const nativeTextareaSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
      nativeTextareaSetter.call(inputElement, message);
      const inputEvent = new InputEvent('input', {
        bubbles: true,
        cancelable: true,
      });
      inputElement.dispatchEvent(inputEvent);
    }
  }

  static submit() {
    const btns = document.querySelectorAll('main form button');
    const btn = btns[btns.length - 1];

    if (btn) {
      btn.focus();
      btn.disabled = false;
      btn.click();
    }
  }
}

window.ChatAsk = ChatAsk;