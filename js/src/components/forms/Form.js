import React from 'react'
import {Button, Form as BootstrapForm} from 'reactstrap'
import Input from './Input'

export default class Form extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      submitted: false,
      form_data: {},
    }
    this.submit = this.submit.bind(this)
    this.set_form_data = this.set_form_data.bind(this)
  }

  async submit (e) {
    e.preventDefault()
    await this.props.root.requests.post('enquiry', this.state.form_data, {expected_statuses: [200, 201]})
    this.setState({submitted: true})
  }

  set_form_data (name, value) {
    const form_data = Object.assign({}, this.state.form_data)
    form_data[name] = value
    this.setState({form_data})
  }

  render () {
    const fields = [
      {name: 'testing', title: 'Title'}
    ]
    return (
      <BootstrapForm>

        {fields.map((field, i) => (
          <Input key={i}
                  field={field}
                  value={this.state.form_data[field.value]}
                  set_value={v => this.set_form_data(field.name, v)}/>
        ))}
        <Button>Submit</Button>
      </BootstrapForm>
    )
  }
}
