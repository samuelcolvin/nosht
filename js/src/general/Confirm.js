import React from 'react'
import {withRouter} from 'react-router-dom'
import {
  Button,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import WithContext from '../utils/context'
import requests from '../utils/requests'

export class ButtonConfirm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      open: false,
      enabled: true,
    }
    if (!this.props.action) {
      throw Error('the "action" props is required for ButtonConfirm')
    }
  }

  async fire () {
    this.setState({enabled: false})
    let data
    try {
      data = await requests.post(this.props.action, this.props.data || null)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({open: false, enabled: true})
    this.props.done && this.props.done(data)
    this.props.redirect_to && this.props.history.push(this.props.redirect_to)
    this.props.success_msg && this.props.ctx.setMessage(this.props.success_msg)
  }

  render () {
    const close = () => this.setState({open: false})
    return [
      <Button key="b"
              onClick={() => this.setState({open: true})}
              color={this.props.btn_color}
              size={this.props.btn_size}
              className={this.props.className}>
        {this.props.btn_icon && <FontAwesomeIcon icon={this.props.btn_icon}/>}
        {this.props.btn_text || 'Confirm'}
      </Button>,
      <Modal key="m" isOpen={this.state.open} toggle={close} size="lg">
        <ModalHeader toggle={close}>{this.props.modal_title}</ModalHeader>
        <ModalBody>
          {this.props.children || 'Are you sure you want to continue?'}
        </ModalBody>
        <ModalFooter>
          <Button color="secondary" onClick={close} disabled={!this.state.enabled}>
            {this.props.close_label || 'Close'}
          </Button>
          <Button color={this.props.btn_color || 'primary'}
                  onClick={this.fire.bind(this)} disabled={!this.state.enabled}>
            {this.props.confirm_label || 'Confirm'}
          </Button>
        </ModalFooter>
      </Modal>,
    ]
  }
}
export default WithContext(withRouter(ButtonConfirm))
