import React, {Component} from 'react'
import Events from '../Events'

export default class Category extends Component {
  constructor (props) {
    super(props)
    this.state = {
      events: [],
    }
    this.setup = this.setup.bind(this)
    this.cat_info = this.cat_info.bind(this)
  }

  componentDidUpdate (prevProps) {
    if (this.props.location.pathname !== prevProps.location.pathname) {
      this.setup()
    }
  }

  componentDidMount () {
    this.setup()
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
      const data = await this.props.requests.get(`cat/${this.props.slug}/`)
      this.setState({events: data.events})
    } catch (err) {
      this.props.setRootState({error: err})
    }
  }

  cat_info () {
    return this.props.company_data.categories.find(c => c.slug === this.props.slug)
  }

  render () {
    console.log(this.state.events)
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
