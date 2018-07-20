import React from 'react'
import {Row, Col} from 'reactstrap'
import {Form} from '../forms/Form'
import Markdown from '../general/Markdown'

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
      data = await this.props.requests.get('/events/categories/')
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.setState({categories: data.categories})
  }

  fields () {
    const c = (this.state.categories || []).map(c => ({value: c.id, display_name: c.name}))
    return [
      {name: 'name', required: true},
      {name: 'public', title: 'Public Event', type: 'bool'},
      {name: 'category', type: 'select', choices: c, required: true},
      {name: 'date', title: 'Event Start', type: 'datetime', required: true},
      {name: 'location', type: 'geolocation', help_text: 'Drag the marker to set the exact event location.'},
      {name: 'ticket_limit', type: 'integer'},
      {name: 'long_description', title: 'Description', type: 'textarea', required: true},
    ]
  }

  finished (r) {
    this.props.history.push(r ? `/dashboard/events/${r.pk}/` : '/dashboard/events/')
  }

  render () {
    const cat_id = this.state.form_data && this.state.form_data.category && parseInt(this.state.form_data.category)
    const cat = cat_id && this.state.categories.find(c => c.id === cat_id)
    return (
      <Row>
        <Col md={8}>
          <h1>Create Event</h1>
          <Form fields={this.fields()}
                action="/events/add/"
                requests={this.props.requests}
                setRootState={this.props.setRootState}
                onChange={d => this.setState({form_data: d})}
                finished={this.finished.bind(this)}/>
        </Col>
        <Col md={4}>
          {cat && <Markdown content={cat.host_advice}/>}
        </Col>
      </Row>
    )
  }
}
