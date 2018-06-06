import React from 'react'
import Events from '../Events'
import {NotFound} from '../utils/Errors'
import OnUpdate from '../utils/OnUpdate'


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
    if (!cat) {
      return
    }
    this.props.setRootState({
      page_title: cat.name,
      background: cat.image,
      extra_menu: null,
      active_page: this.props.match.params.category,
    })
    try {
      const data = await this.requests.get(`cat/${this.props.match.params.category}/`)
      this.setState({events: data.events})
    } catch (error) {
      this.props.setRootState({error})
    }
  }

  cat_info () {
    return this.props.company.categories.find(c => c.slug === this.props.match.params.category)
  }

  render () {
    const cat = this.cat_info()
    if (!cat) {
      return <NotFound location={this.props.location}/>
    }
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
