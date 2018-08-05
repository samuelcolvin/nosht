import React from 'react'
import WithContext from '../context'
import {get_component_name} from '../utils'

export default function PromptUpdate (WrappedComponent) {
  class PromptUpdate extends React.Component {
    constructor (props) {
      super(props)
      this.handlers = []
      this.update = () => this.handlers.map(h => h())
    }

    componentDidUpdate (prevProps) {
      if (this.props.location.pathname !== prevProps.location.pathname) {
        this.update()
      }
    }

    componentDidMount () {
      this.update()
    }

    render () {
      return <WrappedComponent {...this.props} register={h => this.handlers.push(h)}/>
    }
  }
  PromptUpdate.displayName = `PromptUpdate(${get_component_name(WrappedComponent)})`
  return WithContext(PromptUpdate)
}
