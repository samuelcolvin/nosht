import React from 'react'
import {Button, Form as BootstrapForm, ModalBody, ModalFooter} from 'reactstrap'
import Input from './Input'

export default class Form extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      disabled: false,
      form_data: {},
      errors: {},
    }
    this.submit = this.submit.bind(this)
    this.set_form_data = this.set_form_data.bind(this)
  }

  async submit (e) {
    e.preventDefault()
    this.setState({disabled: true})
    const method = this.props.method === 'put' ? this.props.requests.put : this.props.requests.post
    let r
    try {
      r = await method(this.props.action, this.state.form_data, {expected_statuses: [200, 201, 400]})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    if (r.response_status === 400) {
      console.log('error', r)
    } else {
      this.props.set_message(`${this.props.page.singular} updated`)
      this.props.update && this.props.update()
      this.props.toggle_model()
    }
  }

  set_form_data (name, value) {
    const form_data = Object.assign({}, this.state.form_data)
    form_data[name] = value
    this.setState({form_data})
  }

  render () {
    return (
      <BootstrapForm onSubmit={this.submit}>
        <ModalBody>
            {(this.props.fields || []).map((field, i) => (
              <Input key={i}
                      field={field}
                      value={this.state.form_data[field.name]}
                      disabled={this.state.disabled}
                      set_value={v => this.set_form_data(field.name, v)}/>
            ))}
        </ModalBody>
        <ModalFooter>
          <Button type="button" color="secondary" onClick={this.props.toggle_model}>{this.props.cancel || 'Cancel'}</Button>
          <Button type="submit" color="primary">{this.props.save || 'Save'}</Button>
        </ModalFooter>
      </BootstrapForm>
    )
  }
}
