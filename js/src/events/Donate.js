import React from 'react'
import AsModal from '../general/Modal'
import {ModalBody, ModalFooter, ButtonGroup, Button} from 'reactstrap'
import Markdown from '../general/Markdown'
import {Money} from '../general/Money'

class DonateForm extends React.Component {
  render () {
    return [
      <ModalBody key="mb">
        <div>
          <Markdown content={this.props.donation_option.long_description}/>
        </div>
      </ModalBody>,

      <ModalFooter key="mf">
        <ButtonGroup>
          <Button type="button" color="secondary" onClick={this.props.finished}>
            Cancel
          </Button>
          <Button type="submit" color="primary" disabled={true}>
            Donate <Money>{this.props.donation_option.amount}</Money>
          </Button>
        </ButtonGroup>
      </ModalFooter>
    ]
  }
}
export default AsModal(DonateForm)
