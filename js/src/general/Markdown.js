import React from 'react'
import marked from 'marked'

marked.setOptions({
  gfm: true,
  smartLists: true,
  breaks: true,
})

export const to_markdown = (t, sanitize) => {
  if (typeof t === 'string') {
    return marked(t, {sanitize: sanitize !== false}).replace(/<table>/, '<table class="table">')
  } else {
    return null
  }
}

export default ({content, className, sanitize}) => (
  <div className={`markdown ${className || ''}`} dangerouslySetInnerHTML={{__html: to_markdown(content, sanitize)}}/>
)
