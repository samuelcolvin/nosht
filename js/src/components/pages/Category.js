import React from 'react'
import Events from '../Events'
import OnUpdate from '../OnUpdate'


export default class Category extends OnUpdate {
  constructor (props) {
    super(props)
    this.state = {
      events: [],
    }
    this.cat_info = this.cat_info.bind(this)
  }

  async setup () {
    const cat = this.cat_info()
    this.props.setRootState({
      page_title: cat.name,
      background: cat.image,
      extra_menu: null,
      active_page: this.props.slug,
    })
    try {
      const data = await this.requests.get(`cat/${this.props.slug}/`)
      this.setState({events: data.events})
    } catch (err) {
      this.props.setRootState({error: err})
    }
  }

  cat_info () {
    return this.props.company_data.categories.find(c => c.slug === this.props.slug)
  }

  render () {
    return (
      <div className="card-grid">
        <div>
          <h1>{this.cat_info().name}</h1>
          <Events events={this.state.events}/>
        </div>
      </div>
    )
  }
}
