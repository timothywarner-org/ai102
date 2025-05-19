import SVGWrap from './SVGWrap';

export default function WindowMaximize(props: I.SVG) {
  return (
    <SVGWrap {...props} viewBox="0 0 24 24">
      <path fill="currentColor" d="M4 4h16v16H4zm2 4v10h12V8z"/>
    </SVGWrap>
  );
}
