import React from 'react'

export default class PromptUpdate extends React.Component {
  componentDidUpdate (prevProps) {
    if (this.props.location.pathname !== prevProps.location.pathname) {
      this.props.get_data()
    }
  }

  componentDidMount () {
    this.props.get_data()
  }

  render () {
    return <span/>
  }
}
