import React from 'react'
import {
  Button,
  Card,
  CardImg,
  Collapse,
  ModalBody,
  ModalFooter,
  Row,
  Col,
} from 'reactstrap'
import requests from '../utils/requests'
import {DropzoneForm} from '../forms/Drop'
import AsModal from '../general/Modal'
import {image_thumb} from '../utils'

class SetImage extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      images: [],
      drop_form: false,
    }
    this.update_image = this.update_image.bind(this)
  }

  async componentDidMount () {
    let r
    try {
      r = await requests.get(`/categories/${this.props.event.cat_id}/images/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({images: r.images})
  }

  async update_image (image) {
    if (image === this.props.event.image) {
      return
    }
    try {
      await requests.post(`/events/${this.props.event.id}/set-image/existing/`, {image})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.update()
  }

  update_finished () {
    this.props.update()
    this.props.finished()
  }

  render () {
    const m = img => img === this.props.event.image
    const images = this.state.images.slice()
    if (this.props.event.image && !images.includes(this.props.event.image)) {
      images.push(this.props.event.image)
    }
    return [
      <ModalBody key="1">
        <Row>
          {images.map(image => (
            <Col key={image} md="4" className="mb-3">
              <Card inverse color={m(image) ? 'info': 'primary'}
                            className={m(image) ? '': 'cursor-pointer select-image'}
                            onClick={() => this.update_image(image)}>
                <CardImg top src={image_thumb(image)}/>
                <div className="text-center my-1">
                  {m(image) ? 'Current Image' : 'Use this image'}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
        <div className="my-2 text-right">
          <Button onClick={() => this.setState({drop_form: !this.state.drop_form})}>
            Or Upload Custom Image
          </Button>
        </div>
        <Collapse isOpen={this.state.drop_form}>
          <DropzoneForm {...this.props}
                        form_body_class={null}
                        form_footer_class="d-none"
                        update={this.update_finished.bind(this)}
                        action={`/events/${this.props.event.id}/set-image/new/`}/>
        </Collapse>
      </ModalBody>,
      <ModalFooter key="2">
        <Button type="button" color="secondary" onClick={() => this.props.finished()}>
          {this.props.close || 'Close'}
        </Button>
      </ModalFooter>
    ]
  }
}

export default AsModal(SetImage)
