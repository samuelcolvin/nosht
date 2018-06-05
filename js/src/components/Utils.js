import React, { Component } from 'react'
import marked from 'marked'

marked.setOptions({
  gfm: true,
  sanitize: true,
  smartLists: true,
})

export const Error = ({error}) => (
  <div>
    <h3>Error:</h3>
    <p>
      {error.toString()}
      <code>{JSON.stringify(error, null, 2)}</code>
    </p>
  </div>
)

export const Loading = () => (
  <small className="text-muted">loading...</small>
)

export class OnUpdate extends Component {
  constructor (props) {
    super(props)
    this.requests = this.props.requests
    this.setup = this.setup.bind(this)
  }

  componentDidUpdate (prevProps) {
    if (this.props.location.pathname !== prevProps.location.pathname) {
      this.setup()
    }
  }

  componentDidMount () {
    this.setup()
  }

  async setup () {}

  render () {
    return (
      <h1>TODO</h1>
    )
  }
}

export const to_markdown = t => {
  if (t === null || t === undefined) {
    return ''
  } else {
    return marked(t).replace(/<table>/, '<table class="table">')
  }
}

export const Markdown = ({ content }) => (
  <div className="markdown" dangerouslySetInnerHTML={{ __html: to_markdown(content) }} />
)
