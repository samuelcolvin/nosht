import React from 'react'
import {Row, Col, ButtonGroup, Button} from 'reactstrap'
import requests from '../utils/requests'
import {RenderList, RenderDetails, ImageThumbnail, MarkdownPreview, Dash} from '../general/Dashboard'
import {Money} from '../general/Money'
import {ModalForm} from '../forms/Form'
import {ModalDropzoneForm} from '../forms/Drop'

const CAT_FIELDS = [
  {name: 'name', required: true},
  {name: 'live', type: 'bool'},
  {name: 'sort_index', type: 'integer'},
  {name: 'suggested_price', type: 'number', step: 0.01, min: 1, max: 1000},
  {name: 'description', type: 'textarea', required: true},
  {name: 'event_content', type: 'md'},
  {name: 'host_advice', type: 'md'},
  {name: 'booking_trust_message'},
  {name: 'terms_and_conditions_message'},
  {name: 'allow_marketing_message'},
  {name: 'ticket_extra_title'},
  {name: 'ticket_extra_help_text'},
]

export class CategoriesList extends RenderList {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/categories/'
    this.state['buttons'] = [
      {name: 'Add Category', link: this.uri + 'add/'},
    ]
  }

  extra () {
    return <ModalForm {...this.props}
                      title="Add Category"
                      parent_uri={this.uri}
                      success_msg="Category Added"
                      mode="add"
                      action='/categories/add/'
                      fields={CAT_FIELDS}/>
  }
}

const ImageList = ({suggested_images, default_image, image_action}) => (
  (suggested_images && suggested_images.length) ? (
    <div>
      <h4>Suggested Images</h4>
      {suggested_images.map((image, i) => (
        <Row key={i} className="mt-2 pt-2 border-top">
          <Col sm={8}>
            <ImageThumbnail image={image} alt={image}/>
          </Col>
          <Col className="text-right">
            <ButtonGroup>
                <Button onClick={() => image_action('set-default', image)} disabled={default_image === image}>
                  Use for Category
                </Button>
                <Button
                  color="danger"
                  onClick={() => image_action('delete', image)}
                  disabled={default_image === image}>
                  Delete
                </Button>
            </ButtonGroup>
          </Col>
        </Row>
      ))}
    </div>
  ) : <small>No Suggested Images</small>
)

export class CategoriesDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/dashboard/categories/${this.id}/`
    this.state['buttons'] = [
      {name: 'Edit', link: this.uri + 'edit/'},
      {name: 'Add Images', link: this.uri + 'add-image/'},
      {
        name: 'Delete Category',
        action: `/categories/${this.id}/delete/`,
        confirm_msg: 'Are you sure you want to delete this category? This cannot be undone.',
        success_msg: 'Category deleted.',
        redirect_to: '/dashboard/categories/',
      }
    ]
    this.formats = {
      image: {
        wide: true,
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>
      },
      suggested_images: null,
      suggested_price: {
        render: v => v ? <Money>{v}</Money> : <Dash/>
      },
      event_content: {wide: true, render: (v, item) => <MarkdownPreview v={v}/>},
      host_advice: {wide: true, render: (v, item) => <MarkdownPreview v={v}/>},
      terms_and_conditions_message: {title: 'T&C Message'}
    }
  }

  async got_data (data) {
    // this avoids a fouk while suggested_images are being updated
    data.suggested_images = (this.state.item && this.state.item.suggested_images) || []
    await super.got_data(data)
    let r
    try {
      r = await requests.get(`/categories/${this.id}/images/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({item: Object.assign({}, this.state.item, {suggested_images: r.images})})
  }

  async image_action (action, image) {
    try {
      await requests.post(`/categories/${this.id}/images/${action}/`, {image})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.update()
  }

  extra () {
    return [
      <ImageList key="1"
                 image_action={this.image_action.bind(this)}
                 default_image={this.state.item.image}
                 suggested_images={this.state.item.suggested_images}/>,
      <ModalForm title="Edit Category"
                 key="2"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Category Updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/categories/${this.id}/`}
                 fields={CAT_FIELDS}/>,
      <ModalDropzoneForm multiple={true}
                         key="3"
                         parent_uri={this.uri}
                         regex={/add-image\/$/}
                         update={this.update}
                         title="Upload Images"
                         action={`/categories/${this.id}/add-image/`}/>,
    ]
  }
}
