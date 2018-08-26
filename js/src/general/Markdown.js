import React from 'react'
import marked from 'marked'

marked.setOptions({
  gfm: true,
  sanitize: true,
  smartLists: true,
  breaks: true,
})

export const to_markdown = (t) => {
  if (typeof t === 'string') {
    return (
      marked(t)
      .replace(/<table>/g, '<table class="table">')
      .replace(/<a href="http/g, '<a target="_blank" rel="noopener noreferrer" href="http')
    )
  } else {
    return null
  }
}

export default ({content, className}) => (
  <div className={`markdown ${className || ''}`} dangerouslySetInnerHTML={{__html: to_markdown(content)}}/>
)
