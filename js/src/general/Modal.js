import React from 'react'
import {
  Button,
  ButtonGroup,
  Modal,
  ModalFooter as BsModalFooter,
  ModalHeader,
} from 'reactstrap'
import {withRouter} from 'react-router-dom'
import WithContext from '../context'
import {get_component_name} from '../utils'

export const ModalFooter = ({finished, disabled, label}) => (
  <BsModalFooter>
    <ButtonGroup>
      <Button type="button" color="secondary" onClick={() => finished()}>
        Cancel
      </Button>
      <Button type="submit" color="primary" disabled={disabled}>
        {label || 'Book'}
      </Button>
    </ButtonGroup>
  </BsModalFooter>
)

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
      this.toggle_handlers = []
    }

    toggle (r) {
      const shown_new = !this.state.shown
      this.setState({
        shown: shown_new
      })
      this.toggle_handlers.map(h => h(r))
      if (!this.state.shown_new) {
        this.props.history.push(this.props.parent_uri + (r && r.pk ? `${r.pk}/`: ''))
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
        <Modal isOpen={this.state.shown} toggle={() => this.toggle()} size="lg">
          <ModalHeader toggle={() => this.toggle()}>{this.props.title}</ModalHeader>
          <WrappedComponent
            {...this.props}
            finished={this.toggle}
            register_toggle_handler={h => this.toggle_handlers.push(h)}
            form_body_class="modal-body"
            form_footer_class="modal-footer"/>
        </Modal>
      )
    }
  }
  AsModal.displayName = `AsModal(${get_component_name(WrappedComponent)})`
  return WithContext(withRouter(AsModal))
}
