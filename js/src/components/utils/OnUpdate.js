import React, {Component} from 'react'

export default class OnUpdate extends Component {
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
