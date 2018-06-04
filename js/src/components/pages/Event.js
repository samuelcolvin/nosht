import React from 'react'
import OnUpdate from '../OnUpdate'


export default class Event extends OnUpdate {
  constructor (props) {
    super(props)
    this.state = {
      event: null,
    }
    this.cat_info = this.cat_info.bind(this)
  }

  async setup () {
    try {
      const event = await this.requests.get(`event/${this.props.slug}/`)
      this.setState({ event })
      const cat = this.cat_info()
      this.props.setRootState({
        page_title: cat.name,
        background: cat.image,
        extra_menu: null,
        active_page: this.props.slug,
      })
    } catch (err) {
      this.props.setRootState({ error: err })
    }
  }

  cat_info () {
    return this.props.company_data.categories.find(c => c.slug === this.props.cat_slug)
  }

  render () {
    return (
      <div className="card-grid">
        <div>
          <h1>{this.cat_info().name}</h1>
        </div>
      </div>
    )
  }
}
