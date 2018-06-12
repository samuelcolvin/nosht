import React from 'react'
import {Button, Form as BootstrapForm, FormGroup, Label, Input as BsInput, FormText} from 'reactstrap'

const GeneralInput = ({field, value, onChange, custom_type, step}) => (
  <FormGroup>
    <Label for={field.name}>{field.title}</Label>
    <BsInput type={custom_type || field.type || 'text'}
             step={step || null}
             name={field.name}
             id={field.name}
             required={field.required}
             maxLength={field.max_length || 255}
             placeholder={field.title}
             value={value}
             onChange={onChange}/> />
  </FormGroup>
)

const Checkbox = ({field, value, onChange}) => (
  <FormGroup check>
    <Label check>
      <BsInput type="checkbox"
               name={field.name}
               required={field.required}
               checked={value}
               onChange={onChange}/>
      {field.title}
    </Label>
  </FormGroup>
)

const Select = ({field, value, onChange}) => (
  <FormGroup>
    <Label for={field.name}>{field.title}</Label>
    <Input type="select" name={field.name} id={field.name}>
      <option value="">---------</option>
      {field.choices && field.choices.map((choice, i) => (
        <option key={i} value={choice.value}>
          {choice.display_name}
        </option>
      ))}
    </Input>
  </FormGroup>
)

// TODO change
const DatetimeInput = ({field, value, onChange}) => {
  // could use https://stackoverflow.com/a/31162426/949890
  const re_match = value.match(/(.*?)T(.*)/)
  const render_values = {
    date: re_match ? re_match[1] : '',
    time: re_match ? re_match[2] : '',
  }

  const onChange_ = (event) => {
    render_values[event.target.getAttribute('type')] = event.target.value
    onChange({target: {value: render_values.date + 'T' + render_values.time}})
  }
  const required = field.required || render_values.date !== '' || render_values.time !== ''
  return (
    <label>
      {field.title}
      <div>
        <input type="date"
               className="date"
               name={field.name + '-date'}
               required={required}
               value={render_values.date}
               onChange={onChange_}/>
        <input type="time"
               className="time"
               step="300"
               name={field.name + '-time'}
               required={required}
               value={render_values.time}
               onChange={onChange_}/>
      </div>
    </label>
  )
}

const IntegerInput = ({field, value, onChange}) => (
  <GeneralInput field={field} value={value} onChange={onChange} custom_type="number" step="1"/>
)

const INPUT_LOOKUP = {
  'checkbox': Checkbox,
  'select': Select,
  'datetime': DatetimeInput,
  'integer': IntegerInput,
}

export default class Input extends React.Component {
  constructor (props) {
    super(props)
    this.on_change = this.on_change.bind(this)
  }

  on_change (event) {
    const field = this.props.field
    const value = field.type === 'checkbox' ? event.target.checked : event.target.value
    this.props.set_value(value)
  }

  render () {
    const InputComp = INPUT_LOOKUP[this.props.field.type] || GeneralInput
    return (
      <InputComp field={this.props.field} value={this.props.value || ''} onChange={this.on_change}/>
    )
  }
}
