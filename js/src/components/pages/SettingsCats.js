import React from 'react'
import {Row, Col, ButtonGroup, Button} from 'reactstrap'
import {RenderList, RenderDetails, ImageThumbnail} from '../utils/Settings'
import {ModelForm} from '../forms/Form'
import {ModelDropForm} from '../forms/Drop'

const CAT_FIELDS = [
  {name: 'name', required: true},
  {name: 'live', type: 'bool'},
  {name: 'sort_index', type: 'integer'},
  {name: 'description', type: 'textarea', required: true},
  {name: 'event_content', type: 'textarea'},
  {name: 'host_advice', type: 'textarea'},
]

export class CategoriesList extends RenderList {
  constructor (props) {
    super(props)
    this.uri = '/settings/categories/'
    this.state['buttons'] = [
      {name: 'Add Category', link: this.uri + 'add/'},
    ]
  }

  extra () {
    return <ModelForm {...this.props}
                      parent_uri={this.uri}
                      success_msg={`${this.props.page.singular} added`}
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
    this.uri = `/settings/categories/${this.id}/`
    this.skip_keys = ['id', 'suggested_images']
    this.state['buttons'] = [
      {name: 'Edit', link: this.uri + 'edit/'},
      {name: 'Add Images', link: this.uri + 'add-image/'},
    ]
    this.formats = {
      image: {
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>
      }
    }
  }

  async got_data (data) {
    // this avoids a fouk while suggested_images are being updated
    data.suggested_images = (this.state.item && this.state.item.suggested_images) || []
    await super.got_data(data)
    let r
    try {
      r = await this.requests.get(`/categories/${this.id}/images/`)
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    const item = Object.assign({}, this.state.item)
    item.suggested_images = r.images
    this.setState({item})
  }

  async image_action (action, image) {
    try {
      await this.requests.post(`/categories/${this.id}/${action}/`, {image})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.update()
  }

  extra () {
    return [
      <ImageList
        key="1"
        image_action={this.image_action.bind(this)}
        default_image={this.state.item.image}
        suggested_images={this.state.item.suggested_images}/>,
      <ModelForm {...this.props}
                 key="2"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg={`${this.props.page.singular} updated`}
                 initial={this.state.item}
                 update={this.update}
                 action={`/categories/${this.id}/`}
                 fields={CAT_FIELDS}/>,
      <ModelDropForm {...this.props}
                     key="3"
                     parent_uri={this.uri}
                     regex={/add-image\/$/}
                     update={this.update}
                     title="Upload Images"
                     action={`/categories/${this.id}/add-image/`}/>,
    ]
  }
}
