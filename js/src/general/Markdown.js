import React from 'react'
import marked from 'marked'

marked.setOptions({
  gfm: true,
  sanitize: true,
  smartLists: true,
})

export const to_markdown = t => {
  if (t === null || t === undefined) {
    return ''
  } else {
    return marked(t).replace(/<table>/, '<table class="table">')
  }
}

export default ({content}) => (
  <div className="markdown" dangerouslySetInnerHTML={{__html: to_markdown(content)}}/>
)
