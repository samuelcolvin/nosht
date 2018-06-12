import React from 'react'
import {Modal, ModalHeader} from 'reactstrap'
import {get_component_name} from '../utils/Errors'

export default function AsModal (WrappedComponent) {
  class AsModal extends React.Component {
    constructor (props) {
      super(props)
      this.regex = props.regex || (props.mode === 'edit' ? /edit\/$/ : /add\/$/)
      this.path_match = () => Boolean(this.props.location.pathname.match(this.regex))
      this.state = {
        shown: this.path_match()
      }
      this.toggle = this.toggle.bind(this)
    }

    toggle (next_uri) {
      const shown_changed = !this.state.shown
      this.setState({
        shown: shown_changed
      })
      if (!this.state.shown_changed) {
        this.props.history.push(next_uri || this.props.parent_uri)
      }
    }

    componentDidUpdate (prevProps) {
      if (this.props.location !== prevProps.location) {
        this.setState({
          shown: this.path_match(),
        })
      }
    }

    render () {
      const s = this.props.page.singular
      const title = this.props.title || (this.props.mode === 'edit' ? `Edit ${s}` : `Add ${s}`)
      return (
        <Modal isOpen={this.state.shown} toggle={() => this.toggle()} size='lg'>
          <ModalHeader toggle={() => this.toggle()}>{title}</ModalHeader>
          <WrappedComponent toggle_model={this.toggle} {...this.props}/>
        </Modal>
      )
    }
  }
  AsModal.displayName = `AsModal(${get_component_name(WrappedComponent)})`
  return AsModal
}
