import React from 'react'
import {Button, Modal, ModalHeader, ModalBody, ModalFooter} from 'reactstrap'

export default class ModalForm extends React.Component {
  constructor (props) {
    super(props)
    this.regex = /edit\/$/
    this.path_match = () => Boolean(this.props.location.pathname.match(this.regex))
    this.state = {
      modal: this.path_match()
    }
    this.toggle = this.toggle.bind(this)
  }

  toggle () {
    if (this.state.modal) {
      this.props.history.push(this.props.parent_uri)
    }
    this.setState({
      modal: !this.state.modal
    })
  }

  componentDidUpdate (prevProps) {
    if (this.props.location !== prevProps.location) {
      this.setState({
        modal: this.path_match(),
      })
    }
  }

  render () {
    return (
      <div>
        <Modal isOpen={this.state.modal} toggle={this.toggle} className={this.props.className}>
          <ModalHeader toggle={this.toggle}>{this.props.title}</ModalHeader>
          <ModalBody>
            {this.props.children}
          </ModalBody>
          <ModalFooter>
            <Button color="secondary" onClick={this.toggle}>{this.props.cancel || 'Cancel'}</Button>
            <Button color="primary" onClick={this.toggle}>{this.props.save || 'Save'}</Button>
          </ModalFooter>
        </Modal>
      </div>
    )
  }
}
