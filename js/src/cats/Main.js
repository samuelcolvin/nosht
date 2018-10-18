import React from 'react'
import {Link} from 'react-router-dom'
import requests from '../utils/requests'
import {Loading, NotFound} from '../general/Errors'
import PromptUpdate from '../general/PromptUpdate'
import EventCards from '../events/Cards'

class Category extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      events: null,
    }
    this.cat_info = this.cat_info.bind(this)
    this.props.register(this.get_data.bind(this))
  }

  async get_data () {
    const cat = this.cat_info()
    if (!cat) {
      return
    }
    this.setState({events: null})
    this.props.ctx.setRootState({
      page_title: cat.name,
      background: cat.image,
      active_page: this.props.match.params.category,
    })
    try {
      const data = await requests.get(`cat/${this.props.match.params.category}/`)
      this.setState({events: data.events})
    } catch (error) {
      this.props.ctx.setError(error)
    }
  }

  cat_info () {
    return this.props.ctx.company.categories.find(c => c.slug === this.props.match.params.category)
  }

  render () {
    const cat = this.cat_info()
    if (!cat) {
      return <NotFound location={this.props.location}/>
    }
    let create_link = `/create/?cat=${cat.id}`
    if (!this.props.ctx.user || this.props.ctx.user.role === 'guest') {
      create_link = `/signup/?next=${encodeURIComponent(create_link)}`
    }
    return (
      <div>
        <div>
          <h1 className="d-inline-block mr-3">{cat.name}</h1>
          {this.state.events && <Link to={create_link} color="link">
            Host your own {cat.name} event
          </Link>}
        </div>
        <div className="card-grid">
          {this.state.events ? (
            this.state.events.length ?
              <EventCards events={this.state.events}/>
              :
              <span className="text-muted">No Upcoming Events in this Category</span>
            ) : <Loading/>
          }
        </div>
      </div>
    )
  }
}

export default PromptUpdate(Category)
