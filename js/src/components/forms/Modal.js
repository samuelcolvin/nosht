import React from 'react'
import {Modal, ModalHeader} from 'reactstrap'
import Form from './Form'


const get_name = WrappedComponent => (
  WrappedComponent.displayName || WrappedComponent.name || 'Component'
)

export default function AsModal (WrappedComponent) {
  class AsModal extends React.Component {
    constructor (props) {
      super(props)
      this.regex = props.regex || /edit\/$/
      this.path_match = () => Boolean(this.props.location.pathname.match(this.regex))
      this.state = {
        shown: this.path_match()
      }
      this.toggle = this.toggle.bind(this)
    }

    toggle () {
      const shown_changed = !this.state.shown
      this.setState({
        shown: shown_changed
      })
      if (!this.state.shown_changed) {
        this.props.history.push(this.props.parent_uri)
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
      return (
        <Modal isOpen={this.state.shown} toggle={this.toggle}>
          <ModalHeader toggle={this.toggle}>{this.props.title}</ModalHeader>
          <WrappedComponent toggle_model={this.toggle} {...this.props}/>
        </Modal>
      )
    }
  }
  AsModal.displayName = `AsModal(${get_name(WrappedComponent)})`
  return AsModal
}

export const ModelForm = AsModal(Form)
