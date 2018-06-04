import React, {Component} from 'react'
import Events from '../Events'

export default class Category extends Component {
  constructor (props) {
    super(props)
    this.state = {
      events: [],
    }
    console.log(this.props)
  }

  async componentDidMount () {
    try {
      const data = await this.requests.get(`cat/${this.props.category.slug}/`)
      this.setState({events: data.events})
    } catch (err) {
      this.setState({error: err})
    }
  }

  render () {
    return (
      <div className="card-grid">
        <div>
          {/*<h1>{this.props.category.name}</h1>*/}
          <Events events={this.state.events}/>
        </div>
      </div>
    )
  }
}
