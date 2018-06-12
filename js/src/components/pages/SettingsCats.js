import React from 'react'
import {RenderList, RenderDetails} from '../utils/Renderers'
import {ModelForm} from '../forms/Modal'

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
      {name: 'Add Category', link: this.uri + 'add/'}
    ]
  }

  extra () {
    return <ModelForm {...this.props}
                      parent_uri={this.uri}
                      mode="add"
                      action='/categories/add/'
                      fields={CAT_FIELDS}/>
  }
}

export class CategoriesDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/settings/categories/${this.id}/`
    this.state = {
      item: null,
      buttons: [
        {name: 'Edit', link: this.uri + 'edit/'}
      ]
    }
  }

  extra () {
    return <ModelForm {...this.props}
                      parent_uri={this.uri}
                      mode="edit"
                      initial={this.state.item}
                      update={this.update}
                      action={`/categories/${this.id}/`}
                      fields={CAT_FIELDS}/>
  }
}
