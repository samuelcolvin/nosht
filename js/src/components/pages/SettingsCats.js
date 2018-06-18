import React from 'react'
import {RenderList, RenderDetails, ImageThumbnail} from '../utils/Settings'
import {ModelForm} from '../forms/Form'
import {ModelDropForm} from '../forms/Drop'

const CAT_FIELDS = [
  {name: 'name'},
  {name: 'live', type: 'bool'},
  {name: 'sort_index', type: 'integer'},
  {name: 'description', type: 'textarea'},
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
                      mode="add"
                      action='/categories/add/'
                      go_to_new={true}
                      fields={CAT_FIELDS}/>
  }
}

const ImageList = ({images}) => (
  (images && images.length) ? (
    <div>
      <h4>Suggested Images</h4>
      <table className="table">
        <tbody>
          {images.map((image, i) => (
            <tr key={i}>
              <td>
                <ImageThumbnail image={image} alt={image}/>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : <small>No Suggested Images</small>
)

export class CategoriesDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/settings/categories/${this.id}/`
    this.skip_keys = ['id', 'images']
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
    let r
    try {
      r = await this.requests.get(`/categories/${this.id}/images/`)
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    data.images = r.images
    await super.got_data(data)
  }

  extra () {
    return [
      <ImageList key="1" images={this.state.item.images}/>,
      <ModelForm {...this.props}
                 key="2"
                 parent_uri={this.uri}
                 mode="edit"
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
