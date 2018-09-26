import React from 'react'
import {
  Button,
  ButtonGroup,
  ModalBody,
  ModalFooter,
  Row,
  Col,
  Form as BootstrapForm,
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import Input from '../forms/Input'

const FooterLinkEdit = ({index, link, update_link, count}) => {
  const title_field = {
    name: `type_${index}_title`,
    title: 'Link Title',
    required: true,
  }
  const url_field = {
    name: `type_${index}_url`,
    type: 'url',
    title: 'URL',
    required: true,
  }
  const new_tab_field = {
    name: `type_${index}_new_tab`,
    title: 'New tab',
    type: 'bool',
    default: true,
    help_text: 'Wether to open the link in a new table.',
  }
  return (
    <div className="border-bottom-2 py-1 mb-1">
      <Row>
        <Col md="6">
          <Input field={title_field} value={link.title} onChange={v => update_link(index, 'title', v)}/>
        </Col>
        <Col md="6">
          <Input field={url_field} value={link.url} onChange={v => update_link(index, 'url', v)}/>
        </Col>
        <Col md="6">
          <Input field={new_tab_field}
                value={link.new_tab}
                onChange={v => update_link(index, 'new_tab', v)}/>
        </Col>
        <Col md="6" className="text-right mb-1">
          <Button color="danger"
                  size="sm"
                  onClick={() => update_link(index)}
                  disabled={count === 0}>
            <FontAwesomeIcon icon="minus" className="mr-2"/>
            Delete Link
          </Button>
        </Col>
      </Row>
    </div>
  )
}

class FooterLinks extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      links: props.links && props.links.length > 0 ? props.links: [{}],
      savable: false,
    }
  }

  add_link () {
    const links = this.state.links.slice()
    links.push({})
    this.setState({links, savable: true})
  }

  update_link (index, key, value) {
    const links = this.state.links.slice()
    if (!key && !value) {
      // means delete
      links.splice(index, 1)
    } else {
      links[index][key] = value
    }
    this.setState({links, savable: true})
  }

  async submit (e) {
    e.preventDefault()
    try {
      await requests.post('/companies/footer-links/set/', {links: this.state.links.filter(l => l.title && l.url)})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.update()
    this.props.finished()
  }

  render () {
    const count = this.state.links.length
    return (
      <BootstrapForm onSubmit={(this.submit.bind(this))} className="highlight-required">
        <ModalBody key="1">
          <div>
            {this.state.links.map((l, i) => (
              <FooterLinkEdit key={i} index={i} link={l} count={count} update_link={this.update_link.bind(this)}/>
            ))}
          </div>
          <div className="text-right mt-4">
            <Button color="success" size="sm" onClick={this.add_link.bind(this)}>
              <FontAwesomeIcon icon="plus" className="mr-2"/>
              Add Link
            </Button>
          </div>
        </ModalBody>
        <ModalFooter key="2">
          <ButtonGroup>
            <Button type="button" color="secondary" onClick={() => this.props.finished()}>
              {this.props.close || 'Close'}
            </Button>
            <Button type="submit" color="primary" disabled={!this.state.savable}>
              {this.props.save || 'Save'}
            </Button>
          </ButtonGroup>
        </ModalFooter>
      </BootstrapForm>
    )
  }
}

export default AsModal(FooterLinks)
