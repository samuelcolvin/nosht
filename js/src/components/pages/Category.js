import React from 'react'
import Events from '../Events'
import {NotFound} from '../utils/Errors'
import PromptUpdate from '../utils/PromptUpdate'


export default class Category extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      events: [],
    }
    this.cat_info = this.cat_info.bind(this)
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
      const data = await this.props.requests.get(`cat/${this.props.match.params.category}/`)
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
    const prompt_update = <PromptUpdate {...this.props} get_data={this.get_data.bind(this)}/>
    if (!cat) {
      return <NotFound location={this.props.location}>{prompt_update}</NotFound>
    }
    return (
      <div className="card-grid">
        <div>
          <h1>{cat.name}</h1>
          <Events events={this.state.events}/>
        </div>
        {prompt_update}
      </div>
    )
  }
}
