import React from 'react'
import requests from '../utils/requests'
import {RenderList, RenderDetails, ImageThumbnail, MarkdownPreview} from '../general/Dashboard'
import {Money} from '../general/Money'
import {ModalForm} from '../forms/Form'
import {ModalDropzoneForm} from '../forms/Drop'

const FIELDS = [
  {name: 'name', required: true},
  {name: 'category', type: 'select', choices: [], required: true},
  {name: 'live', type: 'bool', default: true},
  {name: 'amount', type: 'number', step: 0.01, min: 1, max: 1000, required: true},
  {name: 'sort_index', type: 'integer'},
  {name: 'short_description', type: 'textarea', required: true},
  {name: 'long_description', type: 'md', required: true},
]

const get_fields = categories => {
  const c = (categories || []).map(c => ({value: c.id, display_name: c.name}))
  return FIELDS.map(f => f.name === 'category' ? Object.assign({}, f, {choices: c}) : f)
}

export class DonationOptionsList extends RenderList {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/donation-options/'
    this.state['buttons'] = [
      {name: 'Add Donation Option', link: this.uri + 'add/'},
    ]
    this.formats = {
      amount: {render: v => <Money>{v}</Money>},
      category_name: {title: 'Category'},
    }
  }

  async got_data (data) {
    await super.got_data(data)
    try {
      const r = await requests.get('/events/categories/')
      this.setState({categories: r.categories})
    } catch (error) {
      this.props.ctx.setError(error)
    }
  }

  extra () {
    return <ModalForm {...this.props}
                      title="Add Donation Option"
                      parent_uri={this.uri}
                      success_msg="Donation Option Added"
                      mode="add"
                      action='/donation-options/add/'
                      fields={get_fields(this.state.categories)}/>
  }
}

export class DonationOptionDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/dashboard/donation-options/${this.id}/`
    this.formats = {
      amount: {render: v => <Money>{v}</Money>},
      category_name: {title: 'Category'},
      long_description: {wide: true, render: v => <MarkdownPreview v={v}/>},
      image: {
        wide: true,
        edit_link: this.uri + 'set-image/',
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>
      },
      category: null,
    }
    this.state['buttons'] = [
      {name: 'Edit', link: this.uri + 'edit/'},
      {
        name: 'Delete Donation Option',
        action: `/donation-options/${this.id}/delete/`,
        confirm_msg: 'Are you sure you want to delete this donation option? This cannot be undone.',
        success_msg: 'Category deleted.',
        redirect_to: '/dashboard/donation-options/',
      }
    ]
  }

  async got_data (data) {
    await super.got_data(data)
    try {
      const r = await requests.get('/events/categories/')
      this.setState({categories: r.categories})
    } catch (error) {
      this.props.ctx.setError(error)
    }
  }

  extra () {
    return [
      <ModalForm title="Edit Donation Option"
                 key="e"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Donation Option Updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/donation-options/${this.id}/`}
                 fields={get_fields(this.state.categories)}/>,
      <ModalDropzoneForm key="d"
                         parent_uri={this.uri}
                         regex={/set-image\/$/}
                         update={this.update}
                         title="Upload Image"
                         action={`donation-options/${this.id}/upload-image/`}
                         help_text="Images must be at least 640px x 480px."/>,
    ]
  }
}
