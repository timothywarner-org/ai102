import SVGWrap from './SVGWrap';

export default function WindowMinimize(props: I.SVG) {
  return (
    <SVGWrap {...props} viewBox="0 0 24 24">
      <path fill="currentColor" d="M20 14H4v-4h16"/>
    </SVGWrap>
  );
}
