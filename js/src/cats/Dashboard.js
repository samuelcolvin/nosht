import React from 'react'
import {Row, Col, ButtonGroup, Button} from 'reactstrap'
import requests from '../utils/requests'
import {RenderList, RenderDetails, ImageThumbnail, MarkdownPreview, Dash} from '../general/Dashboard'
import {Money} from '../general/Money'
import {ModalForm} from '../forms/Form'
import {ModalDropzoneForm} from '../forms/Drop'

const CAT_FIELDS = [
  {
    name: 'name', required: true,
    help_text: 'Public name of this event category.',
  },
  {
    name: 'live', type: 'bool',
    help_text: 'Whether the category is active, untick to make the category unavailable.',
  },
  {
    name: 'sort_index', type: 'integer',
    help_text: 'Number used to order categories on the front page and in the top menu.',
  },
  {
    name: 'suggested_price', type: 'number', step: 0.01, min: 1, max: 1000,
    help_text: 'Default price set when hosts are creating events of this type, ' +
               'leave blank for no suggested price/free.',
  },
  {
    name: 'description', type: 'textarea', required: true,
    help_text: 'Public description of the category, shown on the front page, keep this short and sweet.',
  },
  {
    name: 'event_content', type: 'md',
    help_text: 'Content shown on every event, use this to promote your organisation and the work you do.',
  },
  {
    name: 'host_advice', type: 'md',
    help_text: "Advice to event hosts. This is shown to hosts when they're creating events.",
  },
  {
    name: 'booking_trust_message',
    help_text: 'Message shown just above the login/email form when guests start to book an event.',
  },
  {
    name: 'cover_costs_message',
    help_text: 'Title of the "cover costs" checkbox shown to guests when they\'re booking an event.',
  },
  {
    name: 'cover_costs_percentage', type: 'number', step: 0.01, min: 0.01, max: 100,
    help_text: 'Percentage of the total ticket(s) price which will be added when guests agree to "cover costs".',
  },
  {
    name: 'terms_and_conditions_message',
    help_text: 'Message shown to guests when they\'re requested to agree to terms and conditions, ' +
               'you can use markdown to include a link to your terms and conditions page ' +
               'in the format "[click here](http://www.example.com/terms-and-conditions.html)". ' +
               'If blank guests won\'t be asked to agree to terms and conditions.',
  },
  {
    name: 'allow_marketing_message',
    help_text: "Message shown to guests when they're asked to consent to marketing. If blank they won't be asked.",
  },
  {
    name: 'post_booking_message', type: 'textarea',
    help_text: "Message shown to users after they've bought tickets on the donation page."
  },
  {
    name: 'ticket_extra_title',
    help_text: 'Title of text box where guests can provide extra information for each guest/ticket. ' +
               'e.g. "Dietary requirements and other information".',
  },
  {
    name: 'ticket_extra_help_text',
    help_text: 'Help text under the text box where guests can provide extra information for each guest/ticket.',
  },
]

export class CategoriesList extends RenderList {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/categories/'
    this.state.buttons = [
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
    this.uri = `/dashboard/categories/${this.id()}/`
    this.state.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'},
      {name: 'Add Images', link: this.uri + 'add-image/'},
      {
        name: 'Delete Category',
        action: `/categories/${this.id()}/delete/`,
        confirm_msg: 'Are you sure you want to delete this category? This cannot be undone.',
        success_msg: 'Category deleted.',
        redirect_to: '/dashboard/categories/',
      }
    ]
    this.state.formats = {
      suggested_images: null,
      suggested_price: {
        render: v => v ? <Money>{v}</Money> : <Dash/>
      },
      terms_and_conditions_message: {title: 'T&C Message'},
      cover_costs_message: {index: 1},
      cover_costs_percentage: {index: 2},
      description: {wide: true, index: 3},
      event_content: {wide: true, index: 4, render: (v, item) => <MarkdownPreview v={v}/>},
      host_advice: {wide: true, index: 5, render: (v, item) => <MarkdownPreview v={v}/>},
      image: {
        wide: true,
        index: 6,
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>
      },
    }
  }

  async got_data (data) {
    // this avoids a fouk while suggested_images are being updated
    data.suggested_images = (this.state.item && this.state.item.suggested_images) || []
    await super.got_data(data)
    let r
    try {
      r = await requests.get(`/categories/${this.id()}/images/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.setState({item: Object.assign({}, this.state.item, {suggested_images: r.images})})
  }

  async image_action (action, image) {
    try {
      await requests.post(`/categories/${this.id()}/images/${action}/`, {image})
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
                 action={`/categories/${this.id()}/`}
                 fields={CAT_FIELDS}/>,
      <ModalDropzoneForm multiple={true}
                         key="3"
                         parent_uri={this.uri}
                         regex={/add-image\/$/}
                         update={this.update}
                         title="Upload Images"
                         action={`/categories/${this.id()}/add-image/`}/>,
    ]
  }
}
