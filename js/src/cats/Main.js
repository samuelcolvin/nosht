import React from 'react'
import requests from '../requests'
import {NotFound} from '../general/Errors'
import PromptUpdate from '../general/PromptUpdate'
import EventCards from '../events/Cards'

class Category extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      events: [],
    }
    this.cat_info = this.cat_info.bind(this)
    this.props.register(this.get_data.bind(this))
  }

  async get_data () {
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
      const data = await requests.get(`cat/${this.props.match.params.category}/`)
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
          <h1>{cat.name}</h1>
          <EventCards events={this.state.events}/>
        </div>
      </div>
    )
  }
}

export default PromptUpdate(Category)
