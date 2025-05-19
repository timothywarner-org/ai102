import SVGWrap from './SVGWrap';

export default function Ask(props: I.SVG) {
  return (
    <SVGWrap {...props} viewBox="0 0 24 24">
      <path fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.038 19.927A9.93 9.93 0 0 1 7.7 19L3 20l1.3-3.9C1.976 12.663 2.874 8.228 6.4 5.726c3.526-2.501 8.59-2.296 11.845.48c1.993 1.7 2.93 4.043 2.746 6.346M19 16l-2 3h4l-2 3"/>
    </SVGWrap>
  );
}
