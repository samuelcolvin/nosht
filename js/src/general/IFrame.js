import React from 'react'
import {Loading} from './Errors'


export default ({src, title, id}) => [
  <Loading key="l" classNameOuter="iframe-loading" classNameInner="mx-auto text-muted"/>,
  <iframe
      key="i"
      className="iframe"
      id={id}
      title={title}
      frameBorder="0"
      scrolling="no"
      sandbox="allow-forms allow-scripts"
      src={src}
  />
]
