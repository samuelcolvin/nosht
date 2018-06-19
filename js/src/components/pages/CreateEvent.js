import React from 'react'
import {Row, Col} from 'reactstrap'
import {Form} from '../forms/Form'
import Markdown from '../utils/Markdown'

export default class CreateEvent extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      categories: null,
      form_data: {}
    }
    this.fields = this.fields.bind(this)
  }

  async componentDidMount () {
    let data
    try {
      data = await this.props.requests.get('/event/categories/')
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.setState({categories: data.categories})
  }

  fields () {
    const c = (this.state.categories || []).map(c => ({value: c.id, display_name: c.name}))
    return [
      {name: 'name'},
      {name: 'private_event', type: 'bool'},
      {name: 'category', type: 'select', choices: c, required: true},
      {name: 'date', title: 'Event Start', type: 'datetime'},
      // {name: 'location', type: 'location'},
      {name: 'ticket_limit', type: 'integer'},
      {name: 'description', type: 'textarea'},
    ]
  }

  render () {
    const cat_id = this.state.form_data && this.state.form_data.category && parseInt(this.state.form_data.category)
    const cat = cat_id && this.state.categories.find(c => c.id === cat_id)
    return (
      <Row>
        <Col md={8}>
          <h1>Create Event</h1>
          <Form fields={this.fields()} onChange={d => this.setState({form_data: d})}/>
        </Col>
        <Col md={4}>
          {cat && <Markdown content={cat.host_advice}/>}
        </Col>
      </Row>
    )
  }
}
