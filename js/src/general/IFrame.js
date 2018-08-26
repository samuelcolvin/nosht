import React from 'react'
import {Loading} from './Errors'


export default ({src, title, id}) => (
  <div className="iframe-container">
    <Loading/>
    <iframe
        id={id}
        title={title}
        frameBorder="0"
        scrolling="no"
        sandbox="allow-forms allow-scripts"
        src={src}
    />
  </div>
)
